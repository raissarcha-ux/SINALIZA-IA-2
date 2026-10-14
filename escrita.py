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

from signwriting.visualizer.visualize import signwriting_to_image

PASTA = Path(__file__).parent
ARQUIVO_DICIONARIO = PASTA / "dicionario-libras.tsv"
LINK_SIGNPUDDLE = "https://www.signbank.org/signpuddle2.0/index.php?ui=12&sgn=46"

# Um sinal em FSW (Formal SignWriting) se parece com:  M525x535S2e748483x510S10011501x466
PADRAO_FSW = re.compile(r"(A(S[123][0-9a-f]{2}[0-5][0-9a-f])+)?[BLMR][0-9]{3}x[0-9]{3}(S[123][0-9a-f]{2}[0-5][0-9a-f][0-9]{3}x[0-9]{3})*")


def normalizar(texto):
    """Deixa a palavra em minúsculas e sem acento: 'Mãe' vira 'mae'."""
    texto = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def carregar_dicionario():
    """Lê o dicionario-libras.tsv e devolve uma lista de verbetes:
    [{"palavras": ["casa", "lar"], "fsw": "M5...", "autor": "..."}, ...]
    Se o arquivo não existir, devolve uma lista vazia."""
    if not ARQUIVO_DICIONARIO.exists():
        return []

    verbetes = []
    for linha in ARQUIVO_DICIONARIO.read_text(encoding="utf-8").splitlines():
        partes = linha.split("\t")
        if len(partes) == 3:
            fsw, palavras, autor = partes
            verbetes.append({"palavras": palavras.split("|"), "fsw": fsw, "autor": autor})
    return verbetes


def buscar(verbetes, palavra, limite=6):
    """Procura a palavra no dicionário. Primeiro as iguais, depois as que começam com ela."""
    alvo = normalizar(palavra)
    if not alvo:
        return []
    iguais, comecam = [], []
    for v in verbetes:
        nomes = [normalizar(p) for p in v["palavras"]]
        if alvo in nomes:
            iguais.append(v)
        elif any(n.startswith(alvo) for n in nomes):
            comecam.append(v)
    # Sinais com autor ou fonte conhecidos aparecem primeiro
    def com_credito_primeiro(lista):
        return sorted(lista, key=lambda v: v["autor"] == "")
    return (com_credito_primeiro(iguais) + com_credito_primeiro(comecam))[:limite]


def desenhar(fsw):
    """Transforma o código FSW na imagem do sinal escrito, num fundo branco
    (para aparecer bem também no modo escuro)."""
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
