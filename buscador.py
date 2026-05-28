import time
import requests
import streamlit as st
import pandas as pd
import urllib.parse
import re

st.set_page_config(page_title="Gerador de Leads", page_icon="📍", layout="wide")

st.title("📍 Gerador de Leads — Google Maps")
st.caption("Busca negócios e enriquece com CNPJ, proprietário e Instagram automaticamente")

API_KEY = st.secrets.get("GOOGLE_API_KEY", "") if hasattr(st, "secrets") else ""
if not API_KEY:
    API_KEY = st.text_input("🔑 Chave da Google Places API", type="password", placeholder="AIzaSy...")
else:
    st.success(f"✅ Chave carregada ({API_KEY[:8]}...)")

st.divider()

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    cidade = st.text_input("Cidade", placeholder="Brasília, DF")
with col2:
    categoria = st.text_input("Categoria", placeholder="cafeteria, academia, farmácia...")
with col3:
    raio = st.number_input("Raio (km)", min_value=1, max_value=50, value=5)

buscar = st.button("🔍 Buscar e enriquecer leads", use_container_width=True, type="primary")


# ─── Google Places API (New) ──────────────────────────────────────────────────

def get_coords(cidade, api_key):
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": cidade, "key": api_key}
    ).json()
    if not resp.get("results"):
        return {"latitude": -15.7801, "longitude": -47.9292}
    loc = resp["results"][0]["geometry"]["location"]
    return {"latitude": loc["lat"], "longitude": loc["lng"]}


def buscar_places(cidade, categoria, raio_metros, api_key):
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.id,places.googleMapsUri,nextPageToken"
    }
    resultados = []
    next_page_token = None

    for _ in range(3):
        body = {
            "textQuery": f"{categoria} em {cidade}",
            "languageCode": "pt-BR",
            "maxResultCount": 20,
            "locationBias": {
                "circle": {
                    "center": get_coords(cidade, api_key),
                    "radius": float(raio_metros)
                }
            }
        }
        if next_page_token:
            body["pageToken"] = next_page_token

        resp = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers=headers, json=body
        ).json()

        if "error" in resp:
            st.error(f"❌ Erro Google Places: {resp['error'].get('message', '')}")
            break

        for place in resp.get("places", []):
            resultados.append({
                "place_id": place.get("id", ""),
                "Nome": place.get("displayName", {}).get("text", ""),
                "Endereço": place.get("formattedAddress", ""),
                "Telefone": place.get("nationalPhoneNumber", ""),
                "Site": place.get("websiteUri", ""),
            })

        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break
        time.sleep(1)

    return resultados


# ─── CNPJ + Proprietário ──────────────────────────────────────────────────────

def limpar_nome(nome):
    for s in [" LTDA", " ME", " EPP", " EIRELI", " S/A", " SA"]:
        nome = nome.upper().replace(s, "")
    return nome.strip()


def buscar_cnpj(nome, municipio):
    # Tenta ReceitaWS
    try:
        query = urllib.parse.quote(limpar_nome(nome))
        mun = urllib.parse.quote(municipio.upper())
        resp = requests.get(
            f"https://receitaws.com.br/v1/search?query={query}&municipio={mun}",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        ).json()
        empresas = resp.get("empresas", [])
        if empresas:
            return empresas[0].get("cnpj", "")
    except Exception:
        pass

    # Fallback: BrasilAPI
    try:
        query = urllib.parse.quote(limpar_nome(nome))
        resp = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/search?query={query}&municipio={urllib.parse.quote(municipio)}",
            timeout=10
        ).json()
        if isinstance(resp, list) and resp:
            return resp[0].get("cnpj", "")
    except Exception:
        pass

    return ""


def buscar_socio(cnpj):
    if not cnpj:
        return ""
    try:
        cnpj_limpo = re.sub(r'\D', '', cnpj)
        resp = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}",
            timeout=10
        ).json()
        socios = resp.get("qsa", [])
        for s in socios:
            qual = s.get("qualificacao_socio", "").upper()
            if "ADMIN" in qual or "SÓCIO" in qual or "SOCIO" in qual:
                return s.get("nome_socio", "")
        if socios:
            return socios[0].get("nome_socio", "")
    except Exception:
        pass
    return ""


# ─── Instagram ────────────────────────────────────────────────────────────────

def buscar_instagram(nome, cidade):
    try:
        query = urllib.parse.quote(f"{nome} {cidade} site:instagram.com")
        resp = requests.get(
            f"https://www.google.com/search?q={query}",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        ).text
        matches = re.findall(r'instagram\.com/([a-zA-Z0-9_.]+)', resp)
        ignorar = {"p", "reel", "explore", "accounts", "stories", "tv", "reels", ""}
        for m in matches:
            if m.lower() not in ignorar and len(m) > 2:
                return f"instagram.com/{m}"
    except Exception:
        pass
    return ""


# ─── Pipeline ─────────────────────────────────────────────────────────────────

if buscar:
    if not API_KEY:
        st.warning("Insira sua chave da Google Places API.")
    elif not cidade or not categoria:
        st.warning("Preencha cidade e categoria.")
    else:
        municipio = cidade.split(",")[0].strip()

        with st.spinner(f"🔍 Buscando '{categoria}' em '{cidade}'..."):
            places = buscar_places(cidade, categoria, raio * 1000, API_KEY)

        if not places:
            st.error("Nenhum resultado encontrado.")
        else:
            st.info(f"✅ {len(places)} negócios encontrados. Enriquecendo com CNPJ e proprietário...")

            progress = st.progress(0)
            status = st.empty()
            resultados = []

            for i, place in enumerate(places):
                nome = place["Nome"]
                status.text(f"🔄 {i+1}/{len(places)}: {nome}")

                cnpj = buscar_cnpj(nome, municipio)
                time.sleep(0.5)
                proprietario = buscar_socio(cnpj)
                time.sleep(0.3)
                instagram = buscar_instagram(nome, municipio)
                time.sleep(0.3)

                resultados.append({
                    "Nome da Empresa": nome,
                    "Proprietário": proprietario,
                    "CNPJ": re.sub(r'\D', '', cnpj) if cnpj else "",
                    "Instagram": instagram,
                    "Site": place.get("Site", ""),
                    "Localização": place.get("Endereço", ""),
                    "Telefone": place.get("Telefone", ""),
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
