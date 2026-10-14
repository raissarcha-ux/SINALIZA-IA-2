# =============================================================
#  Sinaliza IA: assistente especialista em Libras para professores
#  Versão 0.1
#
#  Como rodar no seu computador (veja o GUIA.md, Etapa 3):
#      streamlit run app.py
# =============================================================

# --- 1. Bibliotecas -------------------------------------------
# "import" traz para o nosso programa ferramentas que outras pessoas já fizeram.
import os                      # para ler variáveis do sistema (como a chave)
from pathlib import Path       # para encontrar arquivos e pastas

import streamlit as st         # cria a página web (o chat)
from google import genai       # conversa com o Gemini, a IA gratuita do Google
from google.genai import types # tipos de configuração do Gemini


# --- 2. Configurações -----------------------------------------
# Modelos de IA que vamos usar, em ordem de preferência. "gemini-flash-latest"
# aponta sempre para o Flash mais recente (o plano gratuito oferece os Flash).
# Se o primeiro estiver congestionado, o app tenta o próximo da lista.
MODELOS = ["gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]

# A pasta onde este arquivo está. Os outros arquivos são procurados a partir dela.
PASTA = Path(__file__).parent


# --- 3. Montar o "cérebro" da Sinaliza IA ---------------------
# A IA recebe um texto de instruções (quem ela é e como se comportar)
# seguido de toda a base de conhecimento sobre Libras.
def montar_instrucoes():
    instrucoes = (PASTA / "instrucoes.md").read_text(encoding="utf-8")

    partes = [instrucoes, "\n\n# BASE DE CONHECIMENTO\n"]
    # Os textos podem estar na pasta "conhecimento" ou soltos ao lado do app.py
    # (arquivos que começam com número, como 01-historia.md).
    arquivos = list((PASTA / "conhecimento").glob("*.md")) + list(PASTA.glob("[0-9][0-9]-*.md"))
    # sorted() garante a ordem 01, 02, 03...
    for arquivo in sorted(arquivos, key=lambda a: a.name):
        texto = arquivo.read_text(encoding="utf-8")
        partes.append(f"\n\n<<< Arquivo: {arquivo.name} >>>\n{texto}")

    return "".join(partes)


# --- 4. Encontrar a chave secreta (API key) -------------------
# Procuramos a chave em três lugares, nesta ordem:
#   a) no arquivo .streamlit/secrets.toml (ou nos "Secrets" do site, quando publicado)
#   b) numa variável do sistema chamada GEMINI_API_KEY
#   c) se não achar, pedimos para a pessoa colar na barra lateral
def pegar_chave():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass  # não existe secrets.toml: tudo bem, seguimos procurando

    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]

    return st.sidebar.text_input(
        "Cole sua chave do Google AI Studio",
        type="password",
        help="A chave fica só nesta sessão. Veja o GUIA.md, Etapa 1.",
    )


# --- 5. A página ----------------------------------------------
st.set_page_config(page_title="Sinaliza IA", page_icon="🤟")
st.title("🤟 Sinaliza IA")
st.caption("Especialista em Libras para professores · versão 0.1 (em teste)")

# Barra lateral: atalhos e avisos
st.sidebar.header("Atalhos")
ATALHOS = {
    "Plano de aula": "Monte um plano de aula de 50 minutos de Libras para ouvintes do 6º ano, tema família.",
    "Atividade": "Crie uma atividade visual e interativa para praticar expressões não manuais em perguntas.",
    "Gramática": "Explique a diferença entre verbo simples e verbo com concordância, com exemplos em glosa.",
    "História": "Quando e como surgiu a Libras?",
}
pergunta_do_atalho = None
for nome, texto in ATALHOS.items():
    if st.sidebar.button(nome, use_container_width=True):
        pergunta_do_atalho = texto

if st.sidebar.button("🗑️ Nova conversa", use_container_width=True):
    st.session_state.mensagens = []

st.sidebar.divider()
st.sidebar.caption(
    "A Sinaliza IA não vê nem produz vídeo. Sinais variam por região: "
    "confira sempre no dicionário do INES ou com a comunidade surda. "
    "Não escreva dados pessoais de alunos aqui."
)

chave = pegar_chave()
if not chave:
    st.info("Para começar, cole sua chave do Google AI Studio na barra lateral (veja o GUIA.md, Etapa 1).")
    st.stop()  # para o programa aqui até a chave existir


# --- 6. A memória da conversa ---------------------------------
# st.session_state guarda informações enquanto a página está aberta.
# Aqui guardamos a lista de mensagens: [{"papel": "user" ou "model", "texto": "..."}]
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

# Mostra na tela tudo o que já foi conversado
for msg in st.session_state.mensagens:
    avatar = "🧑‍🏫" if msg["papel"] == "user" else "🤟"
    with st.chat_message("user" if msg["papel"] == "user" else "assistant", avatar=avatar):
        st.markdown(msg["texto"])


# --- 7. Receber a pergunta e responder ------------------------
pergunta = st.chat_input("Pergunte sobre Libras ou peça um plano de aula...") or pergunta_do_atalho

if pergunta:
    # Mostra a pergunta da professora
    with st.chat_message("user", avatar="🧑‍🏫"):
        st.markdown(pergunta)

    # Prepara o histórico no formato que o Gemini entende
    historico = [
        types.Content(role=m["papel"], parts=[types.Part(text=m["texto"])])
        for m in st.session_state.mensagens
    ]
    historico.append(types.Content(role="user", parts=[types.Part(text=pergunta)]))

    with st.chat_message("assistant", avatar="🤟"):
        cliente = genai.Client(api_key=chave)
        config = types.GenerateContentConfig(
            system_instruction=montar_instrucoes(),
            temperature=0.4,  # mais baixo = respostas mais cuidadosas e menos "criativas"
        )
        resposta = None
        for modelo in MODELOS:
            try:
                # "stream" faz a resposta aparecer aos poucos, como se estivesse digitando
                pedacos = cliente.models.generate_content_stream(
                    model=modelo, contents=historico, config=config
                )
                primeiro = next(pedacos)  # se o modelo estiver cheio, o erro aparece aqui

                def texto_completo():
                    for p in [primeiro, *pedacos]:
                        if p.text:
                            yield p.text

                resposta = st.write_stream(texto_completo())
                break  # deu certo: sai do "for" e não tenta outros modelos
            except Exception as erro:
                texto_erro = str(erro)
                congestionado = "503" in texto_erro or "UNAVAILABLE" in texto_erro
                sem_cota = "429" in texto_erro or "RESOURCE_EXHAUSTED" in texto_erro
                if (congestionado or sem_cota) and modelo != MODELOS[-1]:
                    continue  # tenta o próximo modelo da lista
                if congestionado:
                    st.warning("Os modelos do Google estão congestionados agora. Espere um pouco e tente de novo.")
                elif sem_cota:
                    st.warning("O limite gratuito de uso foi atingido por agora. Espere um minuto e tente de novo.")
                elif "API key" in texto_erro or "API_KEY" in texto_erro or "403" in texto_erro:
                    st.error("A chave não funcionou. Confira se copiou a chave inteira do Google AI Studio.")
                else:
                    st.error(f"Algo deu errado: {texto_erro}")
                st.stop()

    # Guarda a pergunta e a resposta na memória da conversa
    st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
    st.session_state.mensagens.append({"papel": "model", "texto": resposta})
