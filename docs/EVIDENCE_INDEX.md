# Evidence and submission index

- Repository URL: https://github.com/Habeba-ehab/barq-devops-internship-task
- Final commit: 4f58fa7
- Matching CI run: https://github.com/Habeba-ehab/barq-devops-internship-task/actions/runs/34774096036
- Continuous 12-18 minute video URL: https://drive.google.com/file/d/16f7tht2v92rFyaNwSVvn4xiqiAQNelbp/view?usp=sharing
- Challenge receipt ID: 5f083adfce704224b1a19ddeaa385baa
- Starting video commit: eb24095
- Later documentation-only commits, if any: None. The only commit made during/after the
  video session is the final commit (4f58fa7), containing the live changes made during
  recording (app-03 instance, port 8090).

## Video recording note

Near the end of the recording, I paused briefly, believing I had already pushed a commit;
on realizing it had not been pushed, I ran `git push` and resumed recording immediately,
showing the successful push and CI run. I am disclosing this rather than presenting the
video as uninterrupted.

## Requirement -> file/output -> commit -> video timestamp

Repository, starting commit, clean git status shown
-> terminal output -> eb24095 -> [00:15]

Environment built/started, service health shown
-> terminal output -> eb24095 -> [01:02]

/, /health, /ready, /records, /counter tested
-> terminal output -> eb24095 -> [01:13]

/instance proves both backends serve traffic through NGINX
-> terminal output -> eb24095 -> [02:36]

One backend stopped, continued traffic/errors shown, restored, proven serving again
-> terminal output, failure_test.py -> eb24095 -> [02:53]

Record shown surviving app + PostgreSQL container recreation
-> terminal output -> eb24095 -> [04:36]

validate.py and failure_test.py run live
-> validate.py, failure_test.py -> eb24095 -> [06:17]

One historical-log finding demonstrated
-> log_analysis.md, scripts/q7_timeline.py -> f186be3 -> [07:14]

video_challenge.sh run once, fault diagnosed and fixed without full reset
-> .assessment/challenge.json (receipt 5f083adf...) -> 4f58fa7 -> [07:40]

Public port changed 8080 -> 8090 live, proven
-> .env, docker-compose.yml -> 4f58fa7 -> [09:50]

Third app instance (app-03) added live, all three proven, validation rerun
-> docker-compose.yml, nginx/nginx.conf -> 4f58fa7 -> [11:20]

git status / git diff shown, changes explained, committed on screen, commit hashes shown
-> terminal output -> 4f58fa7 -> [13:05]

Video commits pushed
-> git push output, GitHub Actions run -> 4f58fa7 -> [15:32]