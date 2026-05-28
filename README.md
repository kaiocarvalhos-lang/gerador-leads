# Buscador de Negócios — Google Maps

Busca negócios por cidade e categoria usando a Google Places API e exporta os resultados em CSV.

## Instalação

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Criar arquivo .env com sua chave
cp .env.example .env
# Abra o .env e substitua "sua_chave_aqui" pela sua chave da Google Places API
```

## Como usar

```bash
python buscador.py
```

O script vai perguntar:
- **Cidade** — ex: `Brasília, DF`
- **Categoria** — ex: `cafeteria`, `farmácia`, `academia`, `restaurante`
- **Raio** — em km (padrão: 5km)
- **Enriquecer** — se quiser buscar telefone e website também (mais lento)

## Resultado

Um arquivo CSV com colunas:
- Nome, Endereço, Avaliação, Total de avaliações, Aberto agora, Tipos
- (opcional) Telefone, Website, Link do Maps

## Limites da API gratuita

- $200 de crédito/mês (~6.000 buscas Nearby Search)
- Máximo 60 resultados por busca (3 páginas × 20)
- Com enriquecimento: cada negócio consome 1 chamada extra de Place Details
