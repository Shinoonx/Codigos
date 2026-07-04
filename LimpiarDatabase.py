import pandas as pd


df = pd.read_csv('steam.csv')


columnas_criticas = ['appid', 'name', 'developer', 'publisher', 'genres', 'platforms']
df_limpio = df.dropna(subset=columnas_criticas)


df_limpio['price'] = pd.to_numeric(df_limpio['price'], errors='coerce').fillna(0.0)


df_limpio.to_csv('steam_para_carga.csv', index=False)
print("Archivo 'steam_para_carga.csv' generado con éxito.")