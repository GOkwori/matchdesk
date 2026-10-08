# Metric dictionary

Status: planned engine; no football metric is computed by this foundation API.

Each metric will have a registered formula ID, unit, subject, period/window semantics,
source event IDs and independent expected-value tests. Zero denominators produce
an explicit unavailable value, not a fabricated zero or percentage.

| Formula ID | Definition | Caveat |
|---|---|---|
| shots.v1 | Count distinct shot IDs for subject in [start,end) | Goal markers do not add a second shot |
| goals.v1 | Count accepted goal markers with validated shot links | Corrections and own goals require explicit rules |
| pass_accuracy.v1 | Completed passes / attempted passes | A ratio in [0,1], not a possession measure |
| pass_distance.v1 | sqrt((dx*length/100)^2+(dy*width/100)^2) | Coordinates alone are not metres |
| synthetic_xg.v1 | Sum of simulator shot-quality estimates | Illustrative; not empirically calibrated |
| final_third_entries.v1 | Qualifying controlled transitions over the final-third boundary | Deduplicate sustained possessions |
| attacking_half_recoveries.v1 | Accepted regain events at attacking-normalised x >= 50 | Specify inclusive spatial boundary |
| possession_time.v1 | Controlled ball time / controlled ball time for both teams | Exclude stoppages; not pass-share |
| pressure_proxy.v1 | Defensive actions in specified zone / opponent possession minutes | Proxy for pressure, not tracking-derived truth |
| momentum_proxy.v1 | Versioned weighted rolling features, home minus away | Explain weights; never equate with win probability |

Worked example: seven completed passes from ten attempts gives a 0.7 ratio, rendered
as 70%. A 10-unit x change on a 105-metre pitch represents 10.5 metres before the y
component is included. Tests must independently calculate these expectations.
