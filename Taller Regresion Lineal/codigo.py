import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

advertising = pd.read_csv("automovil_dataset.csv")

print("--- Primeros registros del dataset ---")
print(advertising.head(), "\n")



plt.figure(figsize=(8, 6))
correlation_matrix = advertising.corr()
sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt=".2f")
plt.title("Matriz de Correlación de Variables")
plt.savefig("matriz_correlacion.png")
plt.show()

# 3. Separación de variables dependientes e independientes
X = advertising[['horsepower', 'age', 'mileage', 'engine_size']] # Variables independientes
y = advertising['price'] # Variable dependiente

# Dividir en conjunto de entrenamiento (80%) y prueba (20%)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. Entrenamiento del Modelo de Regresión Lineal
model = LinearRegression()
model.fit(X_train, y_train)

# 5. Evaluación del Modelo (Para Pregunta 2)
y_pred = model.predict(X_test)

r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))

print("--- Métricas de Evaluación ---")
print(f"Coeficiente de Determinación (R^2): {r2:.4f}")
print(f"Error Absoluto Medio (MAE): {mae:.2f}")
print(f"Raíz del Error Cuadrático Medio (RMSE): {rmse:.2f}\n")

# 6. Predicción de un nuevo automóvil (Para Pregunta 3)
nuevo_auto = np.array([[165, 4, 58000, 2.0]])
precio_estimado = model.predict(nuevo_auto)

print("--- Predicción de Nuevo Vehículo ---")
print(f"El precio estimado para el automóvil es: ${precio_estimado[0]:,.2f}")