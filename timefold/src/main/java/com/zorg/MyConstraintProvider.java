package com.zorg;

import org.jgrapht.Graph;
import org.jgrapht.graph.DefaultWeightedEdge;
import org.jgrapht.alg.shortestpath.DijkstraShortestPath;

import ai.timefold.solver.core.api.score.stream.*;
import ai.timefold.solver.core.api.score.buildin.hardsoft.HardSoftScore;
import java.time.LocalTime;
import java.util.Map;
import java.util.HashMap;

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
            minimizeTravel(f),

            // clientAvailability(f),
            // employeeAvailability(f),
            availabilityConstraint(f),
            impossibleCombination(f),

            balanceEmployeeDays(f),
            balanceDays(f),
            assignEmployee(f),
            //sameDayChain(f),
            useAllDays(f),
            encourageMultipleDays(f),
            balanceEmployeeWorkload(f),
            validDayAssignment(f),
            validDay(f),
        };
    }

    private Constraint dogsConstraint(ConstraintFactory f) {
        return f.forEach(Visit.class)
                .filter(v -> v.employee != null &&  v.employee.dogs != -1 && v.employee.dogs < v.client.dogs)
                .penalize("Too many dogs", HardSoftScore.ONE_HARD);
    }

    private Constraint catsConstraint(ConstraintFactory f) {
        return f.forEach(Visit.class)
                .filter(v -> v.employee != null &&  v.employee.cats != -1 && v.employee.cats < v.client.cats)
                .penalize("Too many cats", HardSoftScore.ONE_HARD);
    }

    private Constraint smokeConstraint(ConstraintFactory f) {
        return f.forEach(Visit.class)
                .filter(v -> v.employee != null &&  v.client.smokes && !v.employee.smokes)
                .penalize("Smoking not allowed", HardSoftScore.ONE_HARD);
    }

    private Constraint noOverlap(ConstraintFactory f) {
    return f.forEachUniquePair(Visit.class,
            Joiners.equal(v -> v.employee),
            Joiners.equal(v -> v.day))
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
        .penalize("Outside client window", HardSoftScore.ONE_SOFT);
    }

    private Constraint employeeTimeWindow(ConstraintFactory f) {
    return f.forEach(Visit.class)
        .filter(v -> {
            if (v.startTime == null || v.employee == null) return false;

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

                    // double dist = getDistance(node1, node2, v.graph);
                    double dist = DistanceService.getDistance(node1, node2);
                    return (int)(dist * 100);
                });
    }


    private final Map<String, Double> distanceCache = new HashMap<>();
    
    private double getDistance(long node1, long node2, Graph<Long, DefaultWeightedEdge> graph) {
        long a = Math.min(node1, node2);
        long b = Math.max(node1, node2);
        String key = a + "-" + b; 
        if (distanceCache.containsKey(key)) {
            return distanceCache.get(key);
        }

        try {
            DijkstraShortestPath<Long, DefaultWeightedEdge> dijkstra = new DijkstraShortestPath<>(graph);
            double dist = dijkstra.getPathWeight(node1, node2);
            distanceCache.put(key, dist);
            return dist;
        } catch (Exception e) {
            return 9999; // fallback
        }
    }



        private Constraint balanceEmployeeDays(ConstraintFactory f) {
            return f.forEach(Visit.class)
                    .groupBy(v -> v.employee, v -> v.day, ConstraintCollectors.count())
                    .penalize("Too many visits for one employee on one day", HardSoftScore.ONE_SOFT,
                        (employee, day, count) -> count > 1 ? (count-1)*10 : 0);
        }

        private Constraint balanceDays(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .groupBy(v -> v.day, ConstraintCollectors.count())
                .penalize("Unbalanced days", HardSoftScore.ONE_SOFT,
                    (day, count) -> count * count);
        }

        private Constraint assignEmployee(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .filter(v -> v.employee == null)
                .penalize("Unassigned visit", HardSoftScore.ONE_HARD);
        }

        private Constraint sameDayChain(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .filter(v -> v.previousVisit != null &&
                            v.day != null &&
                            v.previousVisit.day != null &&
                            !v.day.equals(v.previousVisit.day))
                .penalize("Chain across days", HardSoftScore.ONE_HARD);
        }

        private Constraint useAllDays(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .groupBy(v -> v.day, ConstraintCollectors.count())
                .penalize("Too many visits on one day", HardSoftScore.ONE_SOFT,
                    (day, count) -> count * count);
        }

        private Constraint encourageMultipleDays(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .groupBy(v -> v.day, ConstraintCollectors.count())
                .reward("Use more days", HardSoftScore.ONE_SOFT);
        }

        private Constraint balanceEmployeeWorkload(ConstraintFactory f) {
            return f.forEach(Visit.class)
                    .groupBy(v -> v.employee, ConstraintCollectors.count())
                    .penalize("Workload per employee", HardSoftScore.ONE_SOFT,
                        (employee, count) -> (count - 4) * (count - 4)); // streef naar 4 per employee
        }

        private Constraint clientAvailability(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .filter(v -> v.day != null &&
                            v.client.dayRange != null &&
                            !v.client.dayRange.contains(v.day))
                .penalize("Client not available on this day", HardSoftScore.ONE_HARD);
        }

        private Constraint employeeAvailability(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .filter(v -> v.day != null &&
                            v.employee != null &&
                            v.employee.dayRange != null &&
                            !v.employee.dayRange.contains(v.day))
                .penalize("Employee not available on this day", HardSoftScore.ONE_HARD);
        }

        private Constraint validDayAssignment(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .filter(v -> v.day != null && v.employee != null)
                .filter(v ->
                    (v.client.dayRange != null && !v.client.dayRange.contains(v.day)) ||
                    (v.employee.dayRange != null && !v.employee.dayRange.contains(v.day))
                )
                .penalize("Invalid day for client or employee", HardSoftScore.ONE_HARD);
        }

        private Constraint availabilityConstraint(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .filter(v -> v.day != null && v.employee != null)
                .filter(v -> 
                    !v.client.dayRange.contains(v.day) ||
                    !v.employee.dayRange.contains(v.day)
                )
                .penalize("Invalid day (client employee mismatch)", HardSoftScore.ONE_HARD);
        }

        private Constraint impossibleCombination(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .filter(v -> v.employee != null)
                .filter(v -> {
                    if (v.client.dayRange == null || v.employee.dayRange == null) return false;

                    for (Integer d : v.client.dayRange) {
                        if (v.employee.dayRange.contains(d)) {
                            return false; // er is overlap → OK
                        }
                    }
                    return true; // GEEN overlap → onmogelijk
                })
                .penalize("No common available day", HardSoftScore.ONE_HARD);
        }

        private Constraint validDay(ConstraintFactory f) {
            return f.forEach(Visit.class)
                .filter(v -> v.employee != null)
                .filter(v -> v.day != null)
                .filter(v ->
                    !v.employee.dayRange.contains(v.day) ||
                    !v.client.dayRange.contains(v.day)
                )
                .penalize("Invalid day", HardSoftScore.ONE_HARD);
        }

}