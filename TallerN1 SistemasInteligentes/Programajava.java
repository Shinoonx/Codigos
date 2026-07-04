import java.io.*;
import java.util.*;

public class Programajava {
    public static final int TOTAL_NODOS = 150;
    private ArrayList<Integer>[] listaAdyacencia;

    public Programajava() {
        listaAdyacencia = new ArrayList[TOTAL_NODOS];
        for (int i = 0; i < TOTAL_NODOS; i++) {
            listaAdyacencia[i] = new ArrayList<>();
        }
    }

    public static void main(String[] args) {
        Programajava grafo = new Programajava();
        Scanner input = new Scanner(System.in);

        grafo.cargarArchivo("TallerN1 SistemasInteligentes/taller1_nodos.txt");


        grafo.mostrarNodoMasConectado();

        System.out.print("\n2. Ingrese el nodo de inicio para contar nodos alcanzables (0-149): ");
        if (input.hasNextInt()) {
            int inicio = input.nextInt();
            System.out.println("Total de nodos visitados desde " + inicio + ": " + grafo.contarNodosAlcanzables(inicio));
        }

        System.out.print("\n3. Ingrese nodo origen: ");
        int o = input.nextInt();
        System.out.print("Ingrese nodo destino: ");
        int d = input.nextInt();
        System.out.println("¿Existe camino entre " + o + " y " + d + "?: " + (grafo.existeCamino(o, d) ? "Sí" : "No"));

        input.close();
    }

    public void cargarArchivo(String nombreArchivo) {
        File archivo = new File(nombreArchivo);
        try (Scanner sc = new Scanner(archivo)) {
            if (sc.hasNextLine()) sc.nextLine();

            int contador = 0;
            while (sc.hasNextInt()) {
                sc.nextInt(); 
                int origen = sc.nextInt();
                int destino = sc.nextInt();

                if (origen < TOTAL_NODOS && destino < TOTAL_NODOS) {
                    listaAdyacencia[origen].add(destino);
                    contador++;
                }
            }
            System.out.println("Archivo cargado. Se procesaron " + contador + " conexiones.");
        } catch (Exception e) {
            System.err.println("Error al leer el archivo: " + e.getMessage());
        }
    }

    public void mostrarNodoMasConectado() {
        int max = -1;
        int nodo = -1;
        for (int i = 0; i < TOTAL_NODOS; i++) {
            if (listaAdyacencia[i].size() > max) {
                max = listaAdyacencia[i].size();
                nodo = i;
            }
        }
        System.out.println("\n1. Nodo con más conexiones salientes: " + nodo + " (Total: " + max + ")");
    }

    public int contarNodosAlcanzables(int inicio) {
        if (inicio < 0 || inicio >= TOTAL_NODOS) return 0;
        boolean[] visitados = new boolean[TOTAL_NODOS];
        Queue<Integer> cola = new LinkedList<>();

        cola.add(inicio);
        visitados[inicio] = true;
        int contador = 0;

        while (!cola.isEmpty()) {
            int actual = cola.poll();
            contador++;
            for (int vecino : listaAdyacencia[actual]) {
                if (!visitados[vecino]) {
                    visitados[vecino] = true;
                    cola.add(vecino);
                }
            }
        }
        return contador;
    }

    public boolean existeCamino(int o, int d) {
        if (o == d) return true;
        boolean[] visitados = new boolean[TOTAL_NODOS];
        Queue<Integer> cola = new LinkedList<>();

        cola.add(o);
        visitados[o] = true;

        while (!cola.isEmpty()) {
            int actual = cola.poll();
            if (actual == d) return true;
            for (int vecino : listaAdyacencia[actual]) {
                if (!visitados[vecino]) {
                    visitados[vecino] = true;
                    cola.add(vecino);
                }
            }
        }
        return false;
    }
}