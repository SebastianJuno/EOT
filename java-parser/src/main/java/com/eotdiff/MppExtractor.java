package com.eotdiff;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.sf.mpxj.ProjectFile;
import net.sf.mpxj.Task;
import net.sf.mpxj.reader.UniversalProjectReader;

import java.io.File;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.chrono.ChronoLocalDateTime;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class MppExtractor {
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: java -jar mpp-extractor.jar <path-to-mpp>");
            System.exit(1);
        }

        try {
            ProjectFile project = new UniversalProjectReader().read(new File(args[0]));
            List<Map<String, Object>> tasks = new ArrayList<>();

            for (Task task : project.getTasks()) {
                if (task == null || task.getName() == null || task.getID() == null) {
                    continue;
                }

                Map<String, Object> row = new HashMap<>();
                row.put("uid", task.getUniqueID() == null ? task.getID().intValue() : task.getUniqueID().intValue());
                row.put("name", task.getName());
                row.put("wbs", task.getWBS());
                row.put("outline_level", task.getOutlineLevel());
                row.put("is_summary", task.getSummary());
                row.put("start", toDateString(task.getStart()));
                row.put("finish", toDateString(task.getFinish()));
                row.put("baseline_start", toDateString(task.getBaselineStart()));
                row.put("baseline_finish", toDateString(task.getBaselineFinish()));

                if (task.getDuration() != null) {
                    row.put("duration_minutes", (int) Math.round(task.getDuration().convertUnits(net.sf.mpxj.TimeUnit.MINUTES, project.getProjectProperties()).getDuration()));
                } else {
                    row.put("duration_minutes", null);
                }

                Number percentComplete = task.getPercentageComplete();
                row.put("percent_complete", percentComplete == null ? null : percentComplete.doubleValue());

                List<Integer> predecessorUids = new ArrayList<>();
                task.getPredecessors().forEach(rel -> {
                    if (rel.getTargetTask() != null && rel.getTargetTask().getUniqueID() != null) {
                        predecessorUids.add(rel.getTargetTask().getUniqueID().intValue());
                    }
                });
                row.put("predecessors", predecessorUids);

                tasks.add(row);
            }

            Map<String, Object> payload = new HashMap<>();
            payload.put("tasks", tasks);
            System.out.println(GSON.toJson(payload));
        } catch (Exception ex) {
            System.err.println(ex.getMessage());
            System.exit(1);
        }
    }

    private static String toDateString(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof ChronoLocalDateTime<?> dateTime) {
            return dateTime.toLocalDate().toString();
        }
        if (value instanceof LocalDateTime localDateTime) {
            return localDateTime.toLocalDate().toString();
        }
        if (value instanceof Date date) {
            return date.toInstant().atZone(ZoneId.systemDefault()).toLocalDate().toString();
        }
        String text = value.toString();
        return text.length() >= 10 ? text.substring(0, 10) : text;
    }
}
