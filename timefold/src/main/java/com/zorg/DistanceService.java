package com.zorg;

import org.jgrapht.Graph;
import org.jgrapht.graph.DefaultWeightedEdge;
import org.jgrapht.alg.shortestpath.DijkstraShortestPath;

import java.util.HashMap;
import java.util.Map;

/**
 * Central service for shortest path distances using Dijkstra + caching
 */
public class DistanceService {

    // ── Graph input (INIT REQUIRED) ─────────────────────────────
    private static Graph<Long, DefaultWeightedEdge> graph;
    private static DijkstraShortestPath<Long, DefaultWeightedEdge> dijkstra;

    // ── Cache ───────────────────────────────────────────────────
    private static final Map<String, Double> distanceCache = new HashMap<>();

    /**
     * Call this ONCE at startup (AppContext / Main)
     */
    public static void init(Graph<Long, DefaultWeightedEdge> inputGraph) {
        graph = inputGraph;
        dijkstra = new DijkstraShortestPath<>(graph);
    }

    /**
     * Get shortest path distance (cached)
     */
    public static double getDistance(long node1, long node2) {

        if (dijkstra == null) {
            throw new IllegalStateException("DistanceService not initialized. Call init(graph) first.");
        }

        long a = Math.min(node1, node2);
        long b = Math.max(node1, node2);
        String key = a + "-" + b;

        // cache hit
        if (distanceCache.containsKey(key)) {
            return distanceCache.get(key);
        }

        try {
            double dist = dijkstra.getPathWeight(node1, node2);
            distanceCache.put(key, dist);
            return dist;
        } catch (Exception e) {
            return 999999; // fallback if no path
        }
    }

    /**
     * Optional: clear cache (useful when graph changes)
     */
    public static void clearCache() {
        distanceCache.clear();
    }
}