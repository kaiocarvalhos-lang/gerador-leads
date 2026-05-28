import time
import requests
import streamlit as st
import pandas as pd
import urllib.parse

st.set_page_config(page_title="Gerador de Leads", page_icon="📍", layout="wide")

st.title("📍 Gerador de Leads — Google Maps")
st.caption("Busca negócios e enriquece com CNPJ, proprietário e Instagram automaticamente")

API_KEY = st.text_input("🔑 Chave da Google Places API", type="password", placeholder="AIzaSy...")

st.divider()

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    cidade = st.text_input("Cidade", placeholder="Brasília, DF")
with col2:
    categoria = st.text_input("Categoria", placeholder="cafeteria, academia, farmácia...")
with col3:
    raio = st.number_input("Raio (km)", min_value=1, max_value=50, value=5)

buscar = st.button("🔍 Buscar e enriquecer leads", use_container_width=True, type="primary")

BASE_URL = "https://maps.googleapis.com/maps/api/place"


# ─── Google Places ────────────────────────────────────────────────────────────

def geocodificar(cidade, api_key):
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": cidade, "key": api_key}
    ).json()
    if not resp.get("results"):
        return None, None
    loc = resp["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def buscar_places(cidade, categoria, raio_metros, api_key):
    lat, lng = geocodificar(cidade, api_key)
    if not lat:
        return []

    resultados = []
    next_page_token = None
    pagina = 1

    while True:
        params = {
            "location": f"{lat},{lng}",
            "radius": raio_metros,
            "keyword": categoria,
            "key": api_key,
            "language": "pt-BR",
        }
        if next_page_token:
            params = {"pagetoken": next_page_token, "key": api_key}
            time.sleep(2)

        resp = requests.get(f"{BASE_URL}/nearbysearch/json", params=params).json()

        if resp.get("status") not in ("OK", "ZERO_RESULTS"):
            st.error(f"Erro da API Google: {resp.get('status')} — {resp.get('error_message', '')}")
            break

        for place in resp.get("results", []):
            resultados.append({
                "place_id": place.get("place_id", ""),
                "Nome": place.get("name", ""),
                "Endereço": place.get("vicinity", ""),
            })

        next_page_token = resp.get("next_page_token")
        if not next_page_token or pagina >= 3:
            break
        pagina += 1

    return resultados


def buscar_detalhes_place(place_id, api_key):
    resp = requests.get(
        f"{BASE_URL}/details/json",
        params={
            "place_id": place_id,
            "fields": "formatted_phone_number,website,url,formatted_address",
            "key": api_key,
            "language": "pt-BR"
        }
    ).json()
    r = resp.get("result", {})
    return {
        "Site": r.get("website", ""),
        "Telefone": r.get("formatted_phone_number", ""),
        "Localização": r.get("formatted_address", ""),
        "Maps URL": r.get("url", ""),
    }


# ─── Receita Federal (CNPJ) ───────────────────────────────────────────────────

def buscar_cnpj(nome_empresa, municipio):
    """Busca CNPJ na API pública da Receita Federal via BrasilAPI."""
    try:
        # Tenta buscar pelo nome na BrasilAPI
        query = urllib.parse.quote(nome_empresa)
        resp = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/search?query={query}&municipio={urllib.parse.quote(municipio)}",
            timeout=8
        ).json()
        if isinstance(resp, list) and len(resp) > 0:
            empresa = resp[0]
            cnpj = empresa.get("cnpj", "")
            razao = empresa.get("razao_social", "")
            return cnpj, razao
    except Exception:
        pass

    # Fallback: tenta ReceitaWS
    try:
        query = urllib.parse.quote(f"{nome_empresa} {municipio}")
        resp = requests.get(
            f"https://www.receitaws.com.br/v1/search?query={query}",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}
        ).json()
        empresas = resp.get("empresas", [])
        if empresas:
            emp = empresas[0]
            return emp.get("cnpj", ""), emp.get("nome", "")
    except Exception:
        pass

    return "", ""


def buscar_detalhes_cnpj(cnpj):
    """Busca detalhes do CNPJ incluindo sócios/proprietário."""
    if not cnpj:
        return "", ""
    try:
        cnpj_limpo = "".join(filter(str.isdigit, cnpj))
        resp = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}",
            timeout=8
        ).json()
        socios = resp.get("qsa", [])
        proprietario = ""
        if socios:
            # Pega o primeiro sócio/administrador
            proprietario = socios[0].get("nome_socio", "")
        return cnpj_limpo, proprietario
    except Exception:
        return cnpj, ""


# ─── Instagram ────────────────────────────────────────────────────────────────

def buscar_instagram(nome_empresa, cidade):
    """Busca perfil do Instagram via Google Custom Search ou link direto."""
    try:
        query = urllib.parse.quote(f"{nome_empresa} {cidade} instagram")
        resp = requests.get(
            f"https://www.google.com/search?q={query}",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        ).text

        # Procura por links do instagram.com no resultado
        import re
        matches = re.findall(r'instagram\.com/([a-zA-Z0-9_.]+)', resp)
        if matches:
            # Filtra resultados genéricos
            ignorar = {"p", "reel", "explore", "accounts", "stories", "tv", "reels"}
            for m in matches:
                if m.lower() not in ignorar and len(m) > 2:
                    return f"instagram.com/{m}"
    except Exception:
        pass
    return ""


# ─── Pipeline principal ───────────────────────────────────────────────────────

if buscar:
    if not API_KEY:
        st.warning("Insira sua chave da Google Places API.")
    elif not cidade or not categoria:
        st.warning("Preencha cidade e categoria.")
    else:
        # Extrai só o município para buscas
        municipio = cidade.split(",")[0].strip()

        with st.spinner(f"🔍 Buscando '{categoria}' em '{cidade}'..."):
            places = buscar_places(cidade, categoria, raio * 1000, API_KEY)

        if not places:
            st.error("Nenhum resultado encontrado.")
        else:
            st.info(f"✅ {len(places)} negócios encontrados. Enriquecendo dados...")

            progress = st.progress(0)
            status = st.empty()
            resultados = []

            for i, place in enumerate(places):
                nome = place["Nome"]
                status.text(f"🔄 Enriquecendo {i+1}/{len(places)}: {nome}")

                # 1. Detalhes do Google Places
                detalhes = buscar_detalhes_place(place["place_id"], API_KEY)
                time.sleep(0.1)

                # 2. CNPJ + Proprietário
                cnpj_raw, _ = buscar_cnpj(nome, municipio)
                cnpj_formatado, proprietario = buscar_detalhes_cnpj(cnpj_raw)
                time.sleep(0.3)

                # 3. Instagram
                instagram = buscar_instagram(nome, municipio)
                time.sleep(0.5)

                resultados.append({
                    "Nome da Empresa": nome,
                    "Proprietário": proprietario,
                    "CNPJ": cnpj_formatado,
                    "Instagram": instagram,
                    "Site": detalhes.get("Site", ""),
                    "Localização": detalhes.get("Localização", "") or place.get("Endereço", ""),
                    "Telefone": detalhes.get("Telefone", ""),
                })

                progress.progress((i + 1) / len(places))

            status.empty()
            progress.empty()

            df = pd.DataFrame(resultados)

            encontrados = df[df["CNPJ"] != ""].shape[0]
            st.success(f"🎉 {len(df)} leads gerados — {encontrados} com CNPJ encontrado!")

            st.dataframe(df, use_container_width=True)

            csv_data = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="⬇️ Baixar CSV completo",
                data=csv_data,
                file_name=f"leads_{categoria}_{municipio}.csv".replace(" ", "_"),
                mime="text/csv",
                use_container_width=True,
            )
