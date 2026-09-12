# AI usage disclosure

I used Claude (Anthropic) as an interactive assistant throughout this project. I ran every
command myself, on my own machine, and read the real output myself at every step. Claude
did not have direct access to my terminal, files, or environment, it operated based on
what I chose to paste back after running each command.

The general pattern of use across the whole project: Claude suggested a command or a
hypothesis to test and explained the reasoning behind it; I ran it and reported the actual
result; Claude helped interpret that result and proposed the next step; I decided whether
to proceed, and in several cases asked follow-up questions when something did not match my
expectations or when I did not understand the reasoning, which changed the direction of the
investigation (see specific examples below). All final commands, all git commits, and all
decisions to accept a fix as proven were mine, based on evidence I personally observed.

## Debugging and root-cause investigation (Docker/NGINX/app connectivity, Part 2)
- Tool/model: Claude (Claude Sonnet)
- Purpose: Suggested which diagnostic commands to run next based on prior output, and
  explained networking/Docker concepts I did not already know (e.g. what a loopback
  address is, why 0.0.0.0 differs from 127.0.0.1, how Docker's internal DNS/service names
  work) so I could understand, not just execute, each fix.
- Files affected: docker-compose.yml, config/app.env, nginx/nginx.conf, Dockerfile.
- What I actually did: Ran every command myself in my own WSL terminal. When an
  unexpected result came up that Claude had not anticipated (e.g. the Jenkins process
  already occupying port 8080, the Docker Desktop IPv6 networking failure, the restart
  policy not auto-triggering on SIGKILL), I reported the raw output and we investigated it
  together as a new problem, it was not something Claude predicted or pre-scripted.
- How I verified it: I did not accept a stated root cause until I had seen the actual
  failing behavior myself and then personally reran the same test after the fix to confirm
  the specific before/after change (documented per-issue in troubleshooting.md).
- Related commits: all commits listed in troubleshooting.md.

## Log analysis (log_analysis.md)
- Tool/model: Claude (Claude Sonnet)
- Purpose: Helped draft the initial Python scripts used to parse the three log files, and
  explained statistical/log-analysis concepts I did not know beforehand (percentiles,
  what a comma-separated upstream field represents, why sorting timestamps as plain text
  across two different formats produces an incorrect order).
- Files affected: log_analysis.md, scripts/q3_status_counts.py through
  scripts/q7_timeline.py.
- What I actually did: Ran every script myself and read the real output. I pushed back
  when I did not understand a result (e.g. asking directly "so is p95 the fastest request
  of the 5% slowest requests?" and "where do we see the comma example" before accepting an
  explanation), and asked for an additional verification query when a stated conclusion
  (that Phase 2 of the incident continued uninterrupted) did not seem fully checked, which
  led to discovering the more accurate 3-phase timeline actually present in the data.
- How I verified it: Every number in log_analysis.md comes from a script I ran myself
  against the real log files, not from Claude's estimation or memory.
- Related commit: docs: complete log_analysis.md with evidence for all 10 questions.

## Part 3 script implementation (validate.py, failure_test.py, backup.sh, restore.sh, ci.yml)
- Tool/model: Claude (Claude Sonnet)
- Purpose: Drafted the initial version of each script based on the specific requirements
  in TASK.md.
- Files affected: validate.py, failure_test.py, backup.sh, restore.sh,
  .github/workflows/ci.yml.
- What I actually did: Ran each script against my own live environment. For validate.py, I
  ran the negative test myself (stopping app-01 and observing the script correctly report
  4 failing checks and exit 1). For backup.sh/restore.sh, I personally created the test
  record, ran the backup, executed the destructive delete via psql myself, ran the restore,
  and checked the application's own /records endpoint to confirm recovery, this was not
  something I merely watched happen, I typed and ran each of those commands.
- How I verified it: By directly observing real success/failure output from my own runs,
  not by trusting the script's design alone.
- Related commits: feat: implement validate.py with bounded, PASS/FAIL checks;
  feat: implement failure_test.py with real stop/restore/recovery proof;
  feat: implement backup.sh and restore.sh with proven data recovery;
  feat: add CI workflow (checkout, syntax check, build, start, wait, validate).

## Documentation drafting (troubleshooting.md, decisions.md, security_review.md, this file)
- Tool/model: Claude (Claude Sonnet)
- Purpose: Helped organize findings from my own investigation into the structured
  templates provided, and draft the initial wording.
- Files affected: troubleshooting.md, decisions.md, security_review.md, AI_USAGE.md.
- What I actually did: All factual content (commands, outputs, root causes, commit
  references) is drawn from actions I personally performed during this project. I did not
  independently re-verify every sentence of the drafted wording line by line against my
  own memory before pasting it in, given time constraints; the underlying facts being
  documented were things I had already personally observed and tested earlier in the
  project, but the specific phrasing in these documents was largely Claude's drafting,
  organized from my own results.
- Related commits: docs: complete troubleshooting.md with 15 chronological investigation
  entries; docs: complete decisions.md with 6 documented technical decisions;
  docs: complete security_review.md with 9 findings across all required categories.