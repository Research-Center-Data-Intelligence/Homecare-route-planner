package com.zorg;
import java.util.Map;

public class Client {
    public String name;
    public int dogs;
    public int cats;
    public boolean smokes;
    public String timeWindowStart;
    public String timeWindowEnd;
    public double careHours;
    public double latitude;
    public double longitude;
    public long nodeId;

    // Instance methode
    public long findNearestNode(Map<Long, double[]> nodeCoords) {
        long nearestNode = -1;
        double minDist = Double.MAX_VALUE;

        for (Map.Entry<Long, double[]> entry : nodeCoords.entrySet()) {
            double nLat = entry.getValue()[0];
            double nLon = entry.getValue()[1];

            double dist = DistanceUtil.distance(latitude, longitude, nLat, nLon);
            if (dist < minDist) {
                minDist = dist;
                nearestNode = entry.getKey();
            }
        }

        this.nodeId = nearestNode;  // kan nu wel
        return nearestNode;
    }
}