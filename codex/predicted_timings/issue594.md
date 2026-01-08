# Issue 594: Update {day}/metadata.json with predicted timings

_Sample files:_ are in /codex/predicted_timings/QAB5oFK7xx7EoknWgbZ8We under root (for the analysis) and under each {day} for metadata for the day run. 

| # | Field | Description | Format | 
| --------- | ---- | ----------- | ------- |
| 1 | day_start | The earliest start_time for all events submitted in the request. | hh:mm |
| 2 | event_first_finisher | The earliest finish time of runners for _each event_ in the analysis. | hh:mm |
| 3 | day_first_finisher | The earliest finish time of all runners across _all events_ in the analysis. | hh:mm |
| 4 | event_last_finisher | The latest finish time of runners for _each event_ in the analysis. | hh:mm |
| 5 | day_last_finisher | The latest finish time of all runners across _all events_ in the analysis. | hh:mm |
| 6 | day_end | The day_last_finisher value | hh:mm |
| 7 | actual_event_duration | calculated as event_last_finisher - event_first_finisher for each event | hh:mm |
| 8 | day_duration | calculated as day_end - day_start |  hh:mm |

**Sample JSON**
Fields 1-8 will be placed after "events" block, 

```json
{
  "run_id": "kQoTZ5NMc3rmJ9cPPoSbKp",
  "day": "sun",
  "created_at": "2026-01-08T01:29:18.200802Z",
  "status": "PASS",
  "events": {
    "full": {
      "start_time": "07:00",
      "participants": 368
    },
    "10k": {
      "start_time": "07:20",
      "participants": 618
    },
    "half": {
      "start_time": "07:40",
      "participants": 912
    }
  },
  "predicted_timings": {
    "day_start": "07:00",
    "event_first_finisher": {
      "full": "08:14",
      "10k": "08:31",
      "half": "08:45"
    },
    "day_first_finisher": "08:14",
    "event_last_finisher": {
      "full": "13:30",
      "10k": "09:20",
      "half": "10:40"
    },
    "day_last_finisher": "13:30",
    "day_end": "13:30",
    "actual_event_duration": {
      "full": "05:16",
      "10k": "00:49",
      "half": "01:55"
    },
    "day_duration": "06:30"
  }
}
```

**Implementation Notes:**
- Use existing bin data from core computations (DRY principle - do not recalculate)
- All timing values must be in hh:mm format (string, not decimal)
- Store in {day}/metadata.json (day-based, not root metadata.json)
- Calculate during analysis pipeline when generating metadata.json files

---

Comment #1:
During implementation, it was found the underlying data artifacts (.parquet and .json files) do not appear to have values for any of the predicted_timings. As this is a much larger feature request, will make this as a won't do under this issue and the dev branch and create a new issue.

},
"predicted_timings": {
"day_start": "07:00",
"event_first_finisher": {},
"day_first_finisher": "07:02",
"event_last_finisher": {},
"day_last_finisher": "09:40",
"day_end": "09:40",
"actual_event_duration": {},
"day_duration": "02:40"
},

It is clear now that the implementation note "use existing bin data from core computations" was incorrect. 