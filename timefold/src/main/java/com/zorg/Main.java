package com.zorg;

import java.util.*;
import ai.timefold.solver.core.api.solver.*;

import org.jgrapht.*;
import org.jgrapht.graph.*;

import java.io.FileWriter;
import java.io.PrintWriter;

public class Main {

    public static void main(String[] args) throws Exception {

        List<Client> clients = CsvLoader.loadClients();
        List<Employee> employees = CsvLoader.loadEmployees();


        List<EdgeTable> EdgeTable = CsvLoader.loadEdgeTable();


        GraphBuilder.GraphWithCoords result = GraphBuilder.buildGraph(EdgeTable);

        Graph<Long, DefaultWeightedEdge> graph = result.graph;
        Map<Long, double[]> nodeCoords = result.nodeCoords;
        
        DistanceService.init(graph);

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

        // System.out.println("=== FIRST EMPLOYEES ===");

        // for (int z = 0; z < Math.min(5, clients.size()); z++) {
        //     Client e = clients.get(z);

        //     System.out.println(
        //         e.name +
        //         " | dogs=" + e.dogs +
        //         " | cats=" + e.cats +
        //         " | smokes=" + e.smokes +
        //         " | days=" + e.dayRange
        //     );
        // }



        Solution problem = new Solution();
        problem.employees = employees;
        problem.visits = visits;
        problem.dayRange = Arrays.asList(0, 1, 2, 3, 4); // ma-vr
        problem.getTimeRange();  

        SolverFactory<Solution> factory =
                SolverFactory.createFromXmlResource("solverConfig.xml");


        Solver<Solution> solver = factory.buildSolver();

        Solution solved = solver.solve(problem);
        // System.out.println("SCORE: " + solved.getScore());
        // DEBUG
        long assigned = solved.visits.stream()
            .filter(v -> v.employee != null)
            .count();

        System.out.println("Assigned visits: " + assigned + "/" + solved.visits.size());

        System.out.println("=== PLANNING MET ROUTING ===");

        for (Visit v : solved.visits) {
            System.out.println(
                v.client.name + " -> " +
                (v.employee != null ? v.employee.name : "GEEN EMPLOYEE") +
                " om dag " + (v.day != null ? v.day : "NULL") + " " +
                (v.startTime != null ? v.startTime : "NULL")
            );
        }

        writeCsv(solved.visits);


    }

    private static void writeCsv(List<Visit> visits) {
        try (PrintWriter writer = new PrintWriter(new FileWriter("solution_timefold.csv"))) {

            // header
            writer.println("client,employee,day,startTime,lat,lon");

            for (Visit v : visits) {

                String client = v.client != null ? v.client.name : "";
                String employee = v.employee != null ? v.employee.name : "";
                String day = v.day != null ? v.day.toString() : "";
                String time = v.startTime != null ? v.startTime.toString() : "";

                writer.println(
                    client + "," +
                    employee + "," +
                    day + "," +
                    time + "," +
                    v.client.latitude + "," +
                    v.client.longitude
                );
            }

            System.out.println("CSV opgeslagen als solution.csv");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

}