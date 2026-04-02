package com.zorg;

import java.util.*;
import ai.timefold.solver.core.api.solver.*;

import org.jgrapht.*;
import org.jgrapht.graph.*;

public class Main {

    public static void main(String[] args) throws Exception {

        List<Client> clients = CsvLoader.loadClients();
        List<Employee> employees = CsvLoader.loadEmployees();


        List<EdgeTable> EdgeTable = CsvLoader.loadEdgeTable();


        GraphBuilder.GraphWithCoords result = GraphBuilder.buildGraph(EdgeTable);

        Graph<Long, DefaultWeightedEdge> graph = result.graph;
        Map<Long, double[]> nodeCoords = result.nodeCoords;

        for (Client c : clients) {
            c.findNearestNode(nodeCoords);  // vult c.nodeId automatisch
        }



        // maak visits
        List<Visit> visits = new ArrayList<>();

        int i = 0;
        for (Client c : clients) {
            Visit v = new Visit();
            v.id = "visit-" + i++;   // 👈 UNIEK ID
            v.client = c;
            visits.add(v);
        }


        for (Visit v : visits) {
            v.graph = graph; // elke visit weet nu van de graf
        }


        Solution problem = new Solution();
        problem.employees = employees;
        problem.visits = visits;

        SolverFactory<Solution> factory =
                SolverFactory.createFromXmlResource("solverConfig.xml");


        Solver<Solution> solver = factory.buildSolver();
        Solution solved = solver.solve(problem);

        System.out.println("=== PLANNING MET ROUTING ===");

        for (Visit v : solved.visits) {
            System.out.println(
                v.client.name + " -> " +
                v.employee.name + " om " +
                v.startTime +
                " (" + v.client.latitude + "," + v.client.longitude + ")"
            );
        }
    }
}