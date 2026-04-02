package com.zorg;

import java.time.LocalTime;

import ai.timefold.solver.core.api.domain.entity.PlanningEntity;
import ai.timefold.solver.core.api.domain.variable.PlanningVariable;
import ai.timefold.solver.core.api.domain.lookup.PlanningId;

import ai.timefold.solver.core.api.domain.variable.InverseRelationShadowVariable;

import org.jgrapht.*;
import org.jgrapht.graph.*;

@PlanningEntity
public class Visit {

    @PlanningId
    public String id;

    public Client client;

    @PlanningVariable(valueRangeProviderRefs = {"employeeRange"})
    public Employee employee;

    @PlanningVariable(valueRangeProviderRefs = {"timeRange"})
    public LocalTime startTime;

    // 👇 NIEUW (chain)
    @PlanningVariable(valueRangeProviderRefs = {"visitRange"})
    public Visit previousVisit;

    public transient Graph<Long, DefaultWeightedEdge> graph;



}