package com.zorg;

import java.io.*;
import java.util.*;
import org.apache.commons.csv.*;

public class CsvLoader {

    public static List<Client> loadClients() throws Exception {
        List<Client> clients = new ArrayList<>();

        Reader reader = new FileReader("src/main/resources/clients.csv");
        Iterable<CSVRecord> records = CSVFormat.DEFAULT
                .withFirstRecordAsHeader()
                .parse(reader);

        for (CSVRecord r : records) {
            Client c = new Client();

            c.name = r.get("name");
            c.dogs = Integer.parseInt(r.get("dogs"));
            c.cats = Integer.parseInt(r.get("cats"));
            c.smokes = r.get("smokes").equalsIgnoreCase("true");

            c.timeWindowStart = r.get("time_window_start");
            c.timeWindowEnd = r.get("time_window_end");
            c.careHours = Double.parseDouble(r.get("care_hours"));

            String coordinates = r.get("coordinates");

            // Split the coordinates string into latitude and longitude
            String[] coords = coordinates.split(" ");

            // Parse the latitude and longitude separately
            c.latitude = Double.parseDouble(coords[0]);
            c.longitude = Double.parseDouble(coords[1]);

            Set<Integer> allDays = new HashSet<>(Arrays.asList(0, 1, 2, 3, 4));

            // mapping
            Map<String, Integer> dayMap = Map.of(
                "Monday", 0,
                "Tuesday", 1,
                "Wednesday", 2,
                "Thursday", 3,
                "Friday", 4
            );

            // unavailable dagen
            String unavailable = r.get("unavailable_days");

            if (unavailable != null && !unavailable.isBlank()) {
                for (String d : unavailable.split(",")) {
                    Integer num = dayMap.get(d.trim());
                    if (num != null) {
                        allDays.remove(num);
                    }
                }
            }

                    // 👉 FIX: Set → List
            c.dayRange = new ArrayList<>(allDays);
            // wat overblijft = beschikbare dagen
            // c.dayRange = allDays.toArray(new Integer[0]);

            // c.latitude = Double.parseDouble(r.get("latitude"));
            // c.longitude = Double.parseDouble(r.get("longitude"));

            clients.add(c);
        }

        return clients;
    }

    public static List<Employee> loadEmployees() throws Exception {
        List<Employee> employees = new ArrayList<>();

        Reader reader = new FileReader("src/main/resources/employees.csv");
        Iterable<CSVRecord> records = CSVFormat.DEFAULT
                .withFirstRecordAsHeader()
                .parse(reader);

        for (CSVRecord r : records) {
            Employee e = new Employee();

            e.name = r.get("name");
            e.dogs = Integer.parseInt(r.get("dogs"));
            e.cats = Integer.parseInt(r.get("cats"));
            e.smokes = r.get("smokes").equalsIgnoreCase("true");

            e.timeWindowStart = r.get("time_window_start");
            e.timeWindowEnd = r.get("time_window_end");


            String coordinates = r.get("coordinates");

            // Split the coordinates string into latitude and longitude
            String[] coords = coordinates.split(" ");

            // Parse the latitude and longitude separately
            e.latitude = Double.parseDouble(coords[0]);
            e.longitude = Double.parseDouble(coords[1]);

            Set<Integer> days = new HashSet<>();

            Map<String, Integer> dayMap = Map.of(
                "Monday", 0,
                "Tuesday", 1,
                "Wednesday", 2,
                "Thursday", 3,
                "Friday", 4
            );

            String available = r.get("available_days");

            if (available != null && !available.isBlank()) {
                for (String d : available.split(";")) {
                    Integer num = dayMap.get(d.trim());
                    if (num != null) {
                        days.add(num); // ✅ juiste set
                    }
                }
            }

            e.dayRange = new ArrayList<>(days); // ✅ juiste set


            // omzetten naar Integer[]
            // e.dayRange = dayNumbers.toArray(new Integer[0]);



            employees.add(e);
        }

        return employees;
    }


    public static List<EdgeTable> loadEdgeTable() throws Exception {
        List<EdgeTable> EdgeTable = new ArrayList<>();

        Reader reader = new FileReader("src/main/resources/heerlen_edge_table.csv");
        Iterable<CSVRecord> records = CSVFormat.DEFAULT
                .withFirstRecordAsHeader()
                .parse(reader);


        for (CSVRecord r : records) {
            EdgeTable e = new EdgeTable();

            e.u =  Long.parseLong(r.get("u"));
            e.v =  Long.parseLong(r.get("v"));
            e.key = Integer.parseInt(r.get("key"));
            e.name = r.get("name");
            e.highway = r.get("highway");
            e.length = Double.parseDouble(r.get("length"));
            e.speed_kph = Double.parseDouble(r.get("speed_kph"));
            e.travel_time = Double.parseDouble(r.get("travel_time"));
            e.geometry = r.get("geometry");
            e.travelTimeMin = Double.parseDouble(r.get("travel_time_min"));

            EdgeTable.add(e);
        }

        return EdgeTable;
    }


}