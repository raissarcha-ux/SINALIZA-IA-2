# =============================================================
#  Escrita de sinais: busca no dicionário de Libras do SignPuddle
#
#  A Sinaliza IA NUNCA inventa SignWriting. Este arquivo procura o sinal
#  num dicionário escrito pela comunidade (SignPuddle, Libras) e desenha
#  a imagem a partir do código FSW que está lá.
#
#  O dicionário é o arquivo "dicionario-libras.tsv", criado pelo
#  preparar_dicionario.py a partir do arquivo baixado de:
#  https://www.signbank.org/signpuddle2.0/data/spml/sgn46.spml
# =============================================================

import re
import unicodedata
from pathlib import Path

from PIL import Image

from signwriting.formats.swu import is_swu
from signwriting.visualizer.visualize import signwriting_to_image

PASTA = Path(__file__).parent
ARQUIVO_DICIONARIO = PASTA / "dicionario-libras.tsv"
# Sinais que nós mesmos adicionamos (feitos no SignMaker e revisados). Veja o GUIA.md.
ARQUIVO_NOVOS = PASTA / "sinais-novos.tsv"
LINK_SIGNPUDDLE = "https://www.signbank.org/signpuddle2.0/index.php?ui=12&sgn=46"

# Um sinal em FSW (Formal SignWriting) se parece com:  M525x535S2e748483x510S10011501x466
PADRAO_FSW = re.compile(r"(A(S[123][0-9a-f]{2}[0-5][0-9a-f])+)?[BLMR][0-9]{3}x[0-9]{3}(S[123][0-9a-f]{2}[0-5][0-9a-f][0-9]{3}x[0-9]{3})*")


def normalizar(texto):
    """Deixa a palavra em minúsculas e sem acento: 'Mãe' vira 'mae'."""
    texto = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def ler_tsv(arquivo, proprio=False):
    """Lê um arquivo .tsv com uma linha por sinal:  código FSW <TAB> palavras|separadas <TAB> autor
    Linhas que começam com # são comentários e são ignoradas."""
    verbetes = []
    if not arquivo.exists():
        return verbetes
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        partes = linha.split("\t")
        if len(partes) >= 2:
            fsw, palavras = partes[0].strip(), partes[1]
            autor = partes[2].strip() if len(partes) > 2 else ""
            lista = [p.strip() for p in palavras.split("|") if p.strip()]
            verbetes.append({"palavras": lista, "fsw": fsw, "autor": autor, "proprio": proprio,
                             # versão sem acento, já pronta para a busca ficar rápida
                             "nomes": [normalizar(p) for p in lista]})
    return verbetes


def carregar_dicionario():
    """Junta os nossos sinais novos com o dicionário do SignPuddle.
    Devolve uma lista de verbetes: [{"palavras": [...], "fsw": "M5...", "autor": "...", "proprio": ...}]"""
    return ler_tsv(ARQUIVO_NOVOS, proprio=True) + ler_tsv(ARQUIVO_DICIONARIO)


def formas(palavra):
    """Variações simples da palavra: 'obrigada' também procura 'obrigado'; 'casas' procura 'casa'."""
    alvo = normalizar(palavra)
    variacoes = {alvo}
    if len(alvo) > 3 and alvo.endswith("s"):
        variacoes.add(alvo[:-1])
    for v in list(variacoes):
        if v.endswith("a"):
            variacoes.add(v[:-1] + "o")
        elif v.endswith("o"):
            variacoes.add(v[:-1] + "a")
    return variacoes


def buscar(verbetes, palavra, limite=6):
    """Procura a palavra no dicionário, em três níveis:
    1) palavra igual (ou só com plural/gênero diferente), 2) começa com ela,
    3) aparece dentro de uma expressão (ex.: 'dia' em 'bom dia')."""
    alvo = normalizar(palavra)
    if not alvo:
        return []
    variacoes = formas(palavra)
    iguais, comecam, contem = [], [], []
    for v in verbetes:
        nomes = v["nomes"]
        if any(n in variacoes for n in nomes):
            iguais.append(v)
        elif any(n.startswith(alvo) for n in nomes):
            comecam.append(v)
        elif len(alvo) > 2 and any(alvo in n.replace("-", " ").split() for n in nomes):
            contem.append(v)

    # Primeiro os nossos sinais, depois os que têm autor conhecido
    def ordenar(lista):
        return sorted(lista, key=lambda v: (not v.get("proprio"), v["autor"] == ""))
    return (ordenar(iguais) + ordenar(comecam) + ordenar(contem))[:limite]


def desenhar(fsw):
    """Transforma o código FSW na imagem do sinal escrito, num fundo branco
    (para aparecer bem também no modo escuro)."""
    if not (PADRAO_FSW.fullmatch(fsw) or is_swu(fsw)):
        raise ValueError(f"Código de SignWriting inválido: {fsw[:30]}")
    sinal = signwriting_to_image(fsw)
    margem = 12
    fundo = Image.new("RGBA", (sinal.width + 2 * margem, sinal.height + 2 * margem), "white")
    fundo.alpha_composite(sinal.convert("RGBA"), (margem, margem))
    # Dobra o tamanho para ficar mais fácil de ver
    return fundo.resize((fundo.width * 2, fundo.height * 2), Image.LANCZOS)


# Palavras que a pessoa pode ter escrito em maiúsculas sem ser o sinal procurado
_IGNORAR = {"EU", "EM", "DE", "DO", "DA", "O", "A", "E", "SIGNWRITING", "LIBRAS", "ELIS", "SEL", "SW"}


def palavras_da_pergunta(pergunta):
    """Descobre quais sinais a professora quer ver escritos.
    Só responde quando a pergunta fala de escrita de sinais.
    Pega palavras em MAIÚSCULAS (glosas, como CASA) ou entre aspas."""
    texto = normalizar(pergunta)
    if not re.search(r"signwriting|escrita de sinais|escrev|escrit", texto):
        return []
    entre_aspas = re.findall(r"[\"“']([^\"”']{2,30})[\"”']", pergunta)
    maiusculas = [p for p in re.findall(r"\b[A-ZÀ-Ú][A-ZÀ-Ú-]+\b", pergunta) if p not in _IGNORAR]
    vistas, resultado = set(), []
    for p in entre_aspas + maiusculas:
        if normalizar(p) not in vistas:
            vistas.add(normalizar(p))
            resultado.append(p)
    return resultado[:5]
