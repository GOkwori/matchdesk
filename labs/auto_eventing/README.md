# Auto-eventing lab

The challenge asks for auto-eventing: a model run over an incoming video feed that produces the
pass and speed metrics automatically, instead of tagging them by hand. MatchDesk has no match
footage and must not use any, so this lab makes its own. It renders the synthetic match as a
top-down video, runs a detector over the pixels, and scores what the detector found against
the event log.

| Step | File | Sees the log? |
| --- | --- | --- |
| Render the match as video, and keep the ground truth | `render.py` | Yes |
| Find touches, passes, carries, shots, lengths and speeds | `detect.py` | **No**, frames only |
| Match detections to the truth and score them | `run_lab.py` | Yes |

**Rendering.**
- The event log has no continuous ball path, so the renderer builds one. The ball is at each
  event's location at the event's time, and travels to the next location at a seeded,
  realistic speed:
  - passes 11–21 m/s;
  - carries 3.5–6.5 m/s;
  - shots at the log's synthetic shot speed, towards the goal line.
- A ring in the team's colour marks the touch, and stays with the ball while a player runs
  with it.
- Frames carry sensor noise, and about one frame in fifty hides the ball.
- Video: 25 frames a second, 6 pixels a metre, the whole replay to 67:12 (100,800 frames).

**Detection.**
- The ball is the brightest compact blob in each frame. Gaps of up to three hidden frames are
  filled.
- A touch is where the ball's velocity over the next four frames differs most from the last
  four (by at least 3 m/s).
- Each stretch between touches is measured from its first unbroken run of movement:
  - a fast strike (13 m/s or more) that reaches or heads at a goal is a shot;
  - a ball the ringed player keeps is a carry;
  - anything else is a pass.
- The team is read from the ring's colour.

**Results** (whole replay; written to `apps/web/src/studio/generated/auto-eventing.json`, shown
at `/match/nbr-riv/auto-eventing`):
- touches found and their precision;
- event-type and team accuracy;
- touch-to-touch pass length and ball speed error;
- shot speed error against the log's synthetic tracking;
- possession read from the video against `possession_time.v1`.

**Limits.** This is synthetic video rendered from the log, so it is far easier than broadcast
footage:
- no camera movement or perspective;
- no players off the ball;
- a ball that is always the brightest object.

It demonstrates the pipeline and, more importantly, how its output is checked. It is not a claim
of broadcast-grade computer vision.

Run it (about four minutes; needs `numpy` and `ffmpeg`):

```bash
pip install -r labs/auto_eventing/requirements.txt
python3 labs/auto_eventing/run_lab.py --clip apps/web/src/studio/generated/auto-eventing
python3 -m pytest labs/auto_eventing -q
```
