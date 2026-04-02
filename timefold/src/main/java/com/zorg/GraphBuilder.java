package com.zorg;

import org.jgrapht.*;
import org.jgrapht.graph.*;

import java.util.List;
import java.util.HashMap;
import java.util.Map;


public class GraphBuilder {




    public static class GraphWithCoords {
        public Graph<Long, DefaultWeightedEdge> graph;
        public Map<Long, double[]> nodeCoords;

        public GraphWithCoords(Graph<Long, DefaultWeightedEdge> graph, Map<Long, double[]> nodeCoords) {
            this.graph = graph;
            this.nodeCoords = nodeCoords;
        }
    }



   public static GraphWithCoords buildGraph(List<EdgeTable> edges) {
    Graph<Long, DefaultWeightedEdge> graph = new SimpleWeightedGraph<>(DefaultWeightedEdge.class);
    Map<Long, double[]> nodeCoords = new HashMap<>();

    for (EdgeTable edge : edges) {
        long u = edge.u;
        long v = edge.v;
        double weight = edge.travelTimeMin;

        // Parse LINESTRING geometry
        String geom = edge.geometry.replace("LINESTRING (", "").replace(")", "");
        String[] points = geom.split(",");

        // Startpunt
        String[] startPoint = points[0].trim().split(" ");
        double startLon = Double.parseDouble(startPoint[0]);
        double startLat = Double.parseDouble(startPoint[1]);

        // Eindpunt
        String[] endPoint = points[points.length - 1].trim().split(" ");
        double endLon = Double.parseDouble(endPoint[0]);
        double endLat = Double.parseDouble(endPoint[1]);

        // Voeg nodes toe aan map
        nodeCoords.putIfAbsent(u, new double[]{startLat, startLon});
        nodeCoords.putIfAbsent(v, new double[]{endLat, endLon});

        // Voeg vertices en edge toe aan graph
        if (u != v) {
            graph.addVertex(u);
            graph.addVertex(v);

            DefaultWeightedEdge e = graph.addEdge(u, v);
            if (e != null) {
                graph.setEdgeWeight(e, weight);
            }
        } else {
            //System.out.println("Self-loop overgeslagen: " + u);
        }
    }

    return new GraphWithCoords(graph, nodeCoords);
    }
}