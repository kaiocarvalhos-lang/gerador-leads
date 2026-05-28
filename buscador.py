import os
import csv
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
BASE_URL = "https://maps.googleapis.com/maps/api/place"


def buscar_negocios(cidade: str, categoria: str, raio_metros: int = 5000) -> list[dict]:
    """Busca negócios no Google Places e retorna lista de resultados."""

    print(f"\n🔍 Buscando '{categoria}' em '{cidade}' (raio: {raio_metros/1000:.0f}km)...\n")

    # Passo 1: geocodificar a cidade para obter lat/lng
    geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
    geo_params = {"address": cidade, "key": API_KEY}
    geo_resp = requests.get(geo_url, params=geo_params).json()

    if not geo_resp.get("results"):
        print("❌ Cidade não encontrada. Verifique o nome e tente novamente.")
        return []

    location = geo_resp["results"][0]["geometry"]["location"]
    lat, lng = location["lat"], location["lng"]
    print(f"📍 Localização encontrada: {lat}, {lng}")

    # Passo 2: buscar negócios com Nearby Search
    resultados = []
    next_page_token = None
    pagina = 1

    while True:
        print(f"   Buscando página {pagina}...")

        params = {
            "location": f"{lat},{lng}",
            "radius": raio_metros,
            "keyword": categoria,
            "key": API_KEY,
            "language": "pt-BR",
        }

        if next_page_token:
            params = {"pagetoken": next_page_token, "key": API_KEY}
            time.sleep(2)  # Google exige pausa antes de usar next_page_token

        resp = requests.get(f"{BASE_URL}/nearbysearch/json", params=params).json()

        if resp.get("status") not in ("OK", "ZERO_RESULTS"):
            print(f"⚠️  Erro da API: {resp.get('status')} — {resp.get('error_message', '')}")
            break

        for place in resp.get("results", []):
            resultados.append({
                "nome": place.get("name", ""),
                "endereco": place.get("vicinity", ""),
                "avaliacao": place.get("rating", ""),
                "total_avaliacoes": place.get("user_ratings_total", ""),
                "aberto_agora": place.get("opening_hours", {}).get("open_now", ""),
                "tipos": ", ".join(place.get("types", [])),
                "place_id": place.get("place_id", ""),
            })

        next_page_token = resp.get("next_page_token")
        if not next_page_token:
            break

        pagina += 1
        if pagina > 3:  # Google retorna no máximo 3 páginas (60 resultados)
            break

    print(f"\n✅ {len(resultados)} negócios encontrados.")
    return resultados


def enriquecer_detalhes(place_id: str) -> dict:
    """Busca telefone e website de um negócio pelo place_id."""
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,website,url",
        "key": API_KEY,
        "language": "pt-BR",
    }
    resp = requests.get(f"{BASE_URL}/details/json", params=params).json()
    result = resp.get("result", {})
    return {
        "telefone": result.get("formatted_phone_number", ""),
        "website": result.get("website", ""),
        "maps_url": result.get("url", ""),
    }


def exportar_csv(resultados: list[dict], cidade: str, categoria: str, enriquecer: bool = False) -> str:
    """Exporta os resultados para CSV e retorna o nome do arquivo."""

    if enriquecer:
        print("\n📞 Buscando telefone e website (pode demorar um pouco)...")
        for i, r in enumerate(resultados):
            detalhes = enriquecer_detalhes(r["place_id"])
            r.update(detalhes)
            print(f"   {i+1}/{len(resultados)} — {r['nome']}")
            time.sleep(0.2)  # respeita rate limit

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cidade_slug = cidade.replace(" ", "_").replace(",", "").lower()
    categoria_slug = categoria.replace(" ", "_").lower()
    nome_arquivo = f"negocios_{categoria_slug}_{cidade_slug}_{timestamp}.csv"

    campos = ["nome", "endereco", "avaliacao", "total_avaliacoes", "aberto_agora", "tipos"]
    if enriquecer:
        campos += ["telefone", "website", "maps_url"]
    campos.append("place_id")

    with open(nome_arquivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(resultados)

    print(f"\n💾 Arquivo salvo: {nome_arquivo}")
    return nome_arquivo


def main():
    print("=" * 50)
    print("   Buscador de Negócios — Google Maps")
    print("=" * 50)

    if not API_KEY:
        print("❌ Chave da API não encontrada. Crie um arquivo .env com GOOGLE_API_KEY=sua_chave")
        return

    cidade = input("\nCidade (ex: Brasília, DF): ").strip()
    categoria = input("Categoria (ex: cafeteria, farmácia, academia): ").strip()
    raio_input = input("Raio de busca em km (padrão: 5): ").strip()
    raio = int(float(raio_input) * 1000) if raio_input else 5000

    enriquecer_input = input("Buscar telefone e website também? (s/n, padrão: n): ").strip().lower()
    enriquecer = enriquecer_input == "s"

    resultados = buscar_negocios(cidade, categoria, raio)

    if resultados:
        arquivo = exportar_csv(resultados, cidade, categoria, enriquecer)
        print(f"\n🎉 Pronto! Abra o arquivo '{arquivo}' no Excel ou Google Sheets.")
    else:
        print("\nNenhum resultado para exportar.")


if __name__ == "__main__":
    main()
