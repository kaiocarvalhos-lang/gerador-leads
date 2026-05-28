import os
import csv
import time
import requests
import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(page_title="Gerador de Leads", page_icon="📍", layout="centered")

st.title("📍 Gerador de Leads — Google Maps")
st.caption("Busca negócios por cidade e categoria e exporta em CSV")

# Chave da API
API_KEY = st.text_input("🔑 Sua chave da Google Places API", type="password", placeholder="AIzaSy...")

st.divider()

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    cidade = st.text_input("Cidade", placeholder="Brasília, DF")
with col2:
    categoria = st.text_input("Categoria", placeholder="cafeteria, academia...")
with col3:
    raio = st.number_input("Raio (km)", min_value=1, max_value=50, value=5)

enriquecer = st.checkbox("Buscar telefone e website também (mais lento)")

buscar = st.button("🔍 Buscar negócios", use_container_width=True, type="primary")

BASE_URL = "https://maps.googleapis.com/maps/api/place"


def geocodificar(cidade, api_key):
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": cidade, "key": api_key}
    ).json()
    if not resp.get("results"):
        return None, None
    loc = resp["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def buscar_negocios(cidade, categoria, raio_metros, api_key):
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
            st.error(f"Erro da API: {resp.get('status')} — {resp.get('error_message', '')}")
            break

        for place in resp.get("results", []):
            resultados.append({
                "Nome": place.get("name", ""),
                "Endereço": place.get("vicinity", ""),
                "Avaliação": place.get("rating", ""),
                "Total avaliações": place.get("user_ratings_total", ""),
                "Aberto agora": place.get("opening_hours", {}).get("open_now", ""),
                "Tipos": ", ".join(place.get("types", [])),
                "place_id": place.get("place_id", ""),
            })

        next_page_token = resp.get("next_page_token")
        if not next_page_token or pagina >= 3:
            break
        pagina += 1

    return resultados


def buscar_detalhes(place_id, api_key):
    resp = requests.get(
        f"{BASE_URL}/details/json",
        params={"place_id": place_id, "fields": "formatted_phone_number,website,url", "key": api_key, "language": "pt-BR"}
    ).json()
    result = resp.get("result", {})
    return {
        "Telefone": result.get("formatted_phone_number", ""),
        "Website": result.get("website", ""),
        "Link Maps": result.get("url", ""),
    }


if buscar:
    if not API_KEY:
        st.warning("Insira sua chave da Google Places API.")
    elif not cidade or not categoria:
        st.warning("Preencha cidade e categoria.")
    else:
        with st.spinner(f"Buscando '{categoria}' em '{cidade}'..."):
            resultados = buscar_negocios(cidade, categoria, raio * 1000, API_KEY)

        if not resultados:
            st.error("Nenhum resultado encontrado. Verifique a cidade e categoria.")
        else:
            if enriquecer:
                progress = st.progress(0, text="Buscando detalhes...")
                for i, r in enumerate(resultados):
                    detalhes = buscar_detalhes(r["place_id"], API_KEY)
                    r.update(detalhes)
                    time.sleep(0.2)
                    progress.progress((i + 1) / len(resultados), text=f"{i+1}/{len(resultados)} — {r['Nome']}")
                progress.empty()

            # Remove place_id da exibição
            df = pd.DataFrame(resultados).drop(columns=["place_id"])

            st.success(f"✅ {len(resultados)} negócios encontrados!")
            st.dataframe(df, use_container_width=True)

            csv_data = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv_data,
                file_name=f"leads_{categoria}_{cidade}.csv".replace(" ", "_").replace(",", ""),
                mime="text/csv",
                use_container_width=True,
            )
