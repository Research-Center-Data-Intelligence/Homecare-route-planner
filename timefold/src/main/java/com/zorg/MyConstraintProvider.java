package com.zorg;

import org.jgrapht.Graph;
import org.jgrapht.graph.DefaultWeightedEdge;
import org.jgrapht.alg.shortestpath.DijkstraShortestPath;

import ai.timefold.solver.core.api.score.stream.*;
import ai.timefold.solver.core.api.score.buildin.hardsoft.HardSoftScore;
import java.time.LocalTime;
public class MyConstraintProvider implements ConstraintProvider {



    @Override
    public Constraint[] defineConstraints(ConstraintFactory f) {
        return new Constraint[] {
            dogsConstraint(f),
            catsConstraint(f),
            smokeConstraint(f),
            noOverlap(f),
            clientTimeWindow(f),
            employeeTimeWindow(f),
            minimizeTravel(f)
        };
    }

    private Constraint dogsConstraint(ConstraintFactory f) {
        return f.forEach(Visit.class)
                .filter(v -> v.employee.dogs != -1 && v.employee.dogs < v.client.dogs)
                .penalize("Too many dogs", HardSoftScore.ONE_HARD);
    }

    private Constraint catsConstraint(ConstraintFactory f) {
        return f.forEach(Visit.class)
                .filter(v -> v.employee.cats != -1 && v.employee.cats < v.client.cats)
                .penalize("Too many cats", HardSoftScore.ONE_HARD);
    }

    private Constraint smokeConstraint(ConstraintFactory f) {
        return f.forEach(Visit.class)
                .filter(v -> v.client.smokes && !v.employee.smokes)
                .penalize("Smoking not allowed", HardSoftScore.ONE_HARD);
    }

    private Constraint noOverlap(ConstraintFactory f) {
    return f.forEachUniquePair(Visit.class,
            Joiners.equal(v -> v.employee))
        .filter((v1, v2) -> {
            if (v1.startTime == null || v2.startTime == null) return false;

            int dur1 = (int)(v1.client.careHours * 60);
            int dur2 = (int)(v2.client.careHours * 60);

            java.time.LocalTime end1 = v1.startTime.plusMinutes(dur1);
            java.time.LocalTime end2 = v2.startTime.plusMinutes(dur2);

            return v1.startTime.isBefore(end2) && v2.startTime.isBefore(end1);
        })
        .penalize("Overlap", HardSoftScore.ONE_HARD);
    }

    private Constraint clientTimeWindow(ConstraintFactory f) {
    return f.forEach(Visit.class)
        .filter(v -> {
            if (v.startTime == null) return false;


            java.time.LocalTime start = java.time.LocalTime.parse(v.client.timeWindowStart);
            java.time.LocalTime end = java.time.LocalTime.parse(v.client.timeWindowEnd);

            return v.startTime.isBefore(start) || v.startTime.isAfter(end);
        })
        .penalize("Outside client window", HardSoftScore.ONE_HARD);
    }

    private Constraint employeeTimeWindow(ConstraintFactory f) {
    return f.forEach(Visit.class)
        .filter(v -> {
            if (v.startTime == null) return false;

                LocalTime start = LocalTime.parse(v.employee.timeWindowStart);
                LocalTime end = LocalTime.parse(v.employee.timeWindowEnd);

            return v.startTime.isBefore(start) || v.startTime.isAfter(end);
        })
        .penalize("Outside employee window", HardSoftScore.ONE_HARD);
    }

    // private Constraint minimizeTravel(ConstraintFactory f) {
    // return f.forEach(Visit.class)
    //     .filter(v -> v.previousVisit != null)
    //     .penalize("Travel distance", HardSoftScore.ONE_SOFT,
    //         v -> {
    //             Client c1 = v.previousVisit.client;
    //             Client c2 = v.client;

    //             double dist = DistanceUtil.distance(
    //                 c1.latitude, c1.longitude,
    //                 c2.latitude, c2.longitude
    //             );

    //             return (int)(dist * 100); // schaal
    //         });
    // }

    private Constraint minimizeTravel(ConstraintFactory f) {
        return f.forEach(Visit.class)
            .filter(v -> v.previousVisit != null)
            .penalize("Travel distance", HardSoftScore.ONE_SOFT,
                v -> {
                    Client c1 = v.previousVisit.client;
                    Client c2 = v.client;

                    long node1 = c1.nodeId;
                    long node2 = c2.nodeId;

                    double dist;
                    try {
                        DijkstraShortestPath<Long, DefaultWeightedEdge> dijkstra =
                            new DijkstraShortestPath<>(v.graph);
                        dist = dijkstra.getPathWeight(node1, node2);
                    } catch (Exception e) {
                        dist = 9999; // fallback
                    }

                    return (int)(dist * 100);
                });
    }
}