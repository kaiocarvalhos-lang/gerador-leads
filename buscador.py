import time
import requests
import streamlit as st
import pandas as pd
import urllib.parse
import re

st.set_page_config(page_title="Gerador de Leads", page_icon="📍", layout="wide")

st.title("📍 Gerador de Leads — Google Maps")
st.caption("Busca negócios e enriquece com CNPJ, proprietário e Instagram automaticamente")

# Tenta ler do Secrets do Streamlit, senão pede no campo
API_KEY = st.secrets.get("GOOGLE_API_KEY", "") if hasattr(st, "secrets") else ""
if not API_KEY:
    API_KEY = st.text_input("🔑 Chave da Google Places API", type="password", placeholder="AIzaSy...")
else:
    st.success(f"✅ Chave carregada do Secret ({API_KEY[:8]}...)")

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

def buscar_places_new(cidade, categoria, raio_metros, api_key):
    """Usa a Places API (New) com Text Search."""
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.id,places.googleMapsUri"
    }
    
    resultados = []
    next_page_token = None
    
    for _ in range(3):  # máximo 3 páginas
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
        
        resp = requests.post(url, headers=headers, json=body).json()
        
        if "error" in resp:
            st.error(f"❌ Erro da API: {resp['error'].get('message', 'desconhecido')}")
            break
        
        for place in resp.get("places", []):
            resultados.append({
                "place_id": place.get("id", ""),
                "Nome": place.get("displayName", {}).get("text", ""),
                "Endereço": place.get("formattedAddress", ""),
                "Telefone": place.get("nationalPhoneNumber", ""),
                "Site": place.get("websiteUri", ""),
                "Maps URL": place.get("googleMapsUri", ""),
            })
        
        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break
        time.sleep(1)
    
    return resultados


def get_coords(cidade, api_key):
    """Geocodifica cidade para lat/lng."""
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": cidade, "key": api_key}
    ).json()
    
    if not resp.get("results"):
        st.error(f"❌ Cidade não encontrada: {resp.get('status')} — {resp.get('error_message', '')}")
        return {"latitude": -15.7801, "longitude": -47.9292}  # Brasília como fallback
    
    loc = resp["results"][0]["geometry"]["location"]
    return {"latitude": loc["lat"], "longitude": loc["lng"]}


# ─── Receita Federal (CNPJ) ───────────────────────────────────────────────────

def buscar_cnpj_e_socio(nome_empresa, municipio):
    """Busca CNPJ e sócio via BrasilAPI."""
    try:
        query = urllib.parse.quote(f"{nome_empresa}")
        resp = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/search?query={query}&municipio={urllib.parse.quote(municipio)}",
            timeout=8
        ).json()
        if isinstance(resp, list) and len(resp) > 0:
            cnpj = resp[0].get("cnpj", "")
            if cnpj:
                cnpj_limpo = "".join(filter(str.isdigit, cnpj))
                # Busca detalhes com sócios
                det = requests.get(
                    f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}",
                    timeout=8
                ).json()
                socios = det.get("qsa", [])
                proprietario = socios[0].get("nome_socio", "") if socios else ""
                return cnpj_limpo, proprietario
    except Exception:
        pass
    return "", ""


# ─── Instagram ────────────────────────────────────────────────────────────────

def buscar_instagram(nome_empresa, cidade):
    """Busca perfil do Instagram via Google."""
    try:
        query = urllib.parse.quote(f"{nome_empresa} {cidade} site:instagram.com")
        resp = requests.get(
            f"https://www.google.com/search?q={query}",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        ).text
        matches = re.findall(r'instagram\.com/([a-zA-Z0-9_.]+)', resp)
        ignorar = {"p", "reel", "explore", "accounts", "stories", "tv", "reels", ""}
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
        municipio = cidade.split(",")[0].strip()

        with st.spinner(f"🔍 Buscando '{categoria}' em '{cidade}'..."):
            places = buscar_places_new(cidade, categoria, raio * 1000, API_KEY)

        if not places:
            st.error("Nenhum resultado encontrado. Verifique cidade, categoria e se as APIs estão ativadas.")
        else:
            st.info(f"✅ {len(places)} negócios encontrados. Enriquecendo dados...")

            progress = st.progress(0)
            status = st.empty()
            resultados = []

            for i, place in enumerate(places):
                nome = place["Nome"]
                status.text(f"🔄 {i+1}/{len(places)}: {nome}")

                cnpj, proprietario = buscar_cnpj_e_socio(nome, municipio)
                time.sleep(0.3)

                instagram = buscar_instagram(nome, municipio)
                time.sleep(0.3)

                resultados.append({
                    "Nome da Empresa": nome,
                    "Proprietário": proprietario,
                    "CNPJ": cnpj,
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
