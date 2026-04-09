package com.zorg;

import java.time.LocalTime;
import java.util.Arrays;
import java.util.List;

import ai.timefold.solver.core.api.domain.solution.PlanningSolution;
import ai.timefold.solver.core.api.domain.solution.PlanningEntityCollectionProperty;
import ai.timefold.solver.core.api.domain.solution.ProblemFactCollectionProperty;
import ai.timefold.solver.core.api.domain.solution.PlanningScore;
import ai.timefold.solver.core.api.domain.valuerange.ValueRangeProvider;
import ai.timefold.solver.core.api.score.buildin.hardsoft.HardSoftScore;

@PlanningSolution
public class Solution {

    // 👩‍⚕️ Medewerkers (problem facts)
    @ValueRangeProvider(id = "employeeRange")
    @ProblemFactCollectionProperty
    public List<Employee> employees;

    // 📋 Visits (planning entities)
    @PlanningEntityCollectionProperty
    public List<Visit> visits;


    // 💡 Voeg deze range toe voor de chain variable
    @ValueRangeProvider(id = "visitRange")
    public List<Visit> getVisitRange() {
        return visits;
    }


    // ⏰ Mogelijke starttijden
    @ValueRangeProvider(id = "timeRange")
    public List<LocalTime> getTimeRange() {
        return Arrays.asList(
            LocalTime.of(8, 0),
            LocalTime.of(9, 0),
            LocalTime.of(10, 0),
            LocalTime.of(11, 0),
            LocalTime.of(12, 0),
            LocalTime.of(13, 0),
            LocalTime.of(14, 0),
            LocalTime.of(15, 0),
            LocalTime.of(16, 0)
        );
    }

    // 🎯 Score (VERPLICHT!)
    @PlanningScore
    public HardSoftScore score;

    @ValueRangeProvider(id = "dayRange")
    public List<Integer> dayRange;


}