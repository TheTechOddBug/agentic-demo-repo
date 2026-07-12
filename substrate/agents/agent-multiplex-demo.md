---
title: "Agent Substrate: Multiplexing Claude Code Agents Onto Fewer Pods"
date: 2026-07-11
description: >
  A hands-on lab running real Claude Code agents as Substrate actors: three
  agents share a two-pod WorkerPool, Substrate suspends the idle one, and a
  suspended agent resumes mid-loop with its process state intact - proving
  you can run more agents than pods.
tags: [agent-substrate, kubernetes, actors, claude-code, suspend-resume, multiplexing, oversubscription]
author: Michael Levan
---

# More Agents Than Pods

Tldr; Three live Claude Code agents, two worker pods. Substrate suspends
whoever is idle and resumes them on demand - the cluster is oversubscribed
on purpose, and nothing breaks.

Every other lab in this repo drives the counter demo. This one runs a **real
AI agent workload**: each actor is a container running the actual
`@anthropic-ai/claude-code` CLI in a loop - wake, send a task to Claude,
print the answer, idle. The idle window is exactly what Substrate exploits:
agents spend most of their life waiting, so a 2-pod pool can serve 3 (or 30)
of them.

This is the upstream flagship story - the project's demo video shows ~250
agents on 8 pods. Same pattern, demo scale:

1. **Density**: 3 Claude Code actors on a 2-replica `WorkerPool`. The third
   actor cannot run until a slot frees - and you'll see the honest capacity
   signal when it can't.
2. **Mid-loop state survival**: suspend an agent between ticks, resume it,
   and its shell loop continues at the *next* tick number - same process,
   same memory, possibly a different pod.

## What Substrate pieces this uses

| Concept | Where it lives |
|---|---|
| Claude Code workload | `demos/claude-code-multiplex/workload/` - a `node:20-slim` image with the Claude Code CLI and a `run.sh` loop: run `claude --print "$TASK"`, sleep `INTERVAL_SECONDS`, repeat. The tick counter in that loop is our state-survival proof. |
| `WorkerPool` (2 replicas) | `claude-workerpool` in namespace `claude-multiplex-demo`, labeled `workload: claude-multiplex`. The templates bind to it via `workerSelector.matchLabels`. |
| `ActorTemplate` x3 | `agent-luna`, `agent-mars`, `agent-orion` - same image, different `TASK` prompt. `ANTHROPIC_API_KEY` comes from a Secret via `valueFrom.secretKeyRef`. |
| Explicit resume | These agents serve no HTTP, so there's no traffic to wake them through the `atenet-router`. Resume is `kubectl ate resume actor` (the same `Control.ResumeActor` RPC the router would call). |
| Full-state snapshots | The templates set only `snapshotsConfig.location` - no `onPause`/`onCommit` tiering - so a suspend captures the full sandbox (RAM included), unlike the counter template's cheaper `Data` tier. |

---

## Prerequisites

- A GKE cluster with the Substrate control plane installed. Follow the main
  [setup lab](../setup.md) through `./hack/install-ate.sh --deploy-ate-system`.
  (The counter demo is *not* required for this lab.)
- The `kubectl-ate` plugin installed (`go install ./cmd/kubectl-ate` from the
  Substrate repo checkout) and on your `PATH`. It auto-port-forwards to the
  `ate-api-server`, so no manual port-forward is needed for the CLI steps.
- An **Anthropic API key**. The agents make real Claude API calls.
- Local tools beyond the setup lab's list:

| Tool | Why |
|---|---|
| `docker` with `buildx` | The workload is a Dockerfile image (Node + Claude Code CLI), not a Go binary - `ko` doesn't apply, so the deploy step builds and pushes it with `docker buildx`. |
| `jq` | The deploy step uses it to resolve the pushed image's sha256 digest. |

> **This lab costs real money in two ways**: each RUNNING agent calls the
> Anthropic API every 45 seconds, and the workload image build pushes to your
> registry. Suspend the actors when you're not actively demoing (Step 6's
> cleanup does this), and don't leave the demo running overnight.

Run everything from the root of your Substrate repo checkout, with your env
file sourced (it carries `BUCKET_NAME` and `KO_DOCKER_REPO`, which the deploy
step requires):

```bash
source .ate-dev-env.sh
```

Confirm the control plane is healthy before starting:

```bash
kubectl get pods -n ate-system
```

---

## Step 1 - Deploy the demo (templates, pool, Secret)

Export your Anthropic key (`read -s` keeps it out of your shell history):

```bash
read -s ANTHROPIC_API_KEY && export ANTHROPIC_API_KEY
```

Deploy. `BUCKET_NAME` and `KO_DOCKER_REPO` are already in your environment
from the env file:

```bash
./hack/install-ate.sh --deploy-demo-claude-code-multiplex
```

This builds the workload image with `docker buildx`, pushes it to
`${KO_DOCKER_REPO}/claude-multiplex-demo-workload`, and applies a rendered
manifest containing:

- the `claude-multiplex-demo` namespace,
- an `anthropic-api-key` Secret (the templates consume it via
  `valueFrom.secretKeyRef` - your key never appears in the ActorTemplate spec),
- the 2-replica `WorkerPool` `claude-workerpool`,
- three `ActorTemplate`s: `agent-luna`, `agent-mars`, `agent-orion`.

Wait for the templates to build their golden snapshots (this runs each
workload once and checkpoints it - expect a few minutes and a few log lines
of Claude output in the bucket-bound snapshot run):

```bash
kubectl wait --for=condition=Ready \
  actortemplate/agent-luna actortemplate/agent-mars actortemplate/agent-orion \
  -n claude-multiplex-demo --timeout=10m
```

And confirm the two worker pods are up:

```bash
kubectl get workerpool,pods -n claude-multiplex-demo
```

Two pods. That number does not change for the rest of the lab - hold that
thought.

---

## Step 2 - Create three agents

Actors live in an atespace (the tenancy boundary - see the
[multi-tenancy lab](../isolation/session-identity-multi-tenancy.md)). Create
one for the demo, then one actor per template:

```bash
kubectl ate create atespace agents

kubectl ate create actor luna  --template claude-multiplex-demo/agent-luna  --atespace agents
kubectl ate create actor mars  --template claude-multiplex-demo/agent-mars  --atespace agents
kubectl ate create actor orion --template claude-multiplex-demo/agent-orion --atespace agents

kubectl ate get actors --atespace agents
```

All three show `STATUS_SUSPENDED` with no `ATEOM POD`. **Three agents exist
and consume zero pods.** That's the resting state of a Substrate fleet - and
at this point the pattern already scales in your head: 300 suspended agents
would also consume zero pods.

---

## Step 3 - Wake two agents and watch real Claude output

Resume two of the three (the pool has exactly two slots):

```bash
kubectl ate resume actor luna --atespace agents
kubectl ate resume actor mars --atespace agents

kubectl ate get actors --atespace agents
```

`luna` and `mars` go `STATUS_RESUMING` → `STATUS_RUNNING`, each bound to a
different worker in the `ATEOM POD` column. Now stream an agent's logs and
watch it work:

```bash
kubectl ate logs actor luna --atespace agents -f
```

You'll see the loop ticking:

```
[demo-actor:luna] === tick 3 at 14:22:07Z ===
[demo-actor:luna] running: Tell me one short, surprising fact about the Moon. One sentence.
---
The Moon is moving away from Earth at about 3.8 centimeters per year...
---
[demo-actor:luna] tick 3 done; sleeping 45s
```

That's a genuine Claude API round-trip from inside a gVisor-sandboxed actor.
**Note the current tick number** - you'll use it in Step 5.

> Don't expect the ticks to start at 1. The golden snapshot was captured
> after the workload had already started (that's the point - actors hydrate
> from a warm checkpoint, not a cold boot), so the loop resumes wherever the
> snapshot left it. `Ctrl-C` the log stream when you've noted the tick.

---

## Step 4 - The density squeeze: three agents, two slots

Try to wake the third agent while both workers are held:

```bash
kubectl ate resume actor orion --atespace agents
```

If both slots are still occupied, this fails with something like
`no free workers available`. **That error is the demo, not a bug** - it's an
oversubscribed system telling you the truth about capacity. Confirm who's
holding the slots:

```bash
kubectl ate get workers
```

Both workers show an assigned actor. Now do what Substrate does on idle -
free a slot - and retry:

```bash
kubectl ate suspend actor mars --atespace agents
kubectl ate resume actor orion --atespace agents

kubectl ate get actors --atespace agents
```

`orion` is `STATUS_RUNNING`, `mars` is `STATUS_SUSPENDED` (checkpointed to
the bucket, slot released). Three agents have all done real work; at no point
did a third pod exist.

> **Idle-suspension does this for you in steady state.** Substrate
> automatically suspends actors after a quiet window, so a fleet of looping
> agents self-rotates through the pool - that's the rotation the upstream
> demo video shows. In a live walkthrough the manual suspend is the reliable
> path (you control the timing); if you wait a few minutes instead, you may
> see actors flip to `STATUS_SUSPENDED` on their own. Same end state.

---

## Step 5 - Resume mid-loop: the process picks up where it left off

`mars` was suspended in the middle of its infinite loop. Because this
template snapshots **full state** (no `onPause`/`onCommit` tiering), that
checkpoint includes the process's memory - the shell loop's `TICK` variable
included.

Note the last tick `mars` printed before the suspend, then wake it:

```bash
kubectl ate suspend actor orion --atespace agents   # free a slot first
kubectl ate resume actor mars --atespace agents
kubectl ate logs actor mars --atespace agents -f
```

Read the log stream against what you noted:

- **The tick number continues** - if it was at tick 6 before suspend, the
  next line is tick 7. The loop did not restart.
- **No new startup banner** - `[demo-actor:mars] starting; task=...` appears
  only when the process boots. Its absence means this is the *same process*,
  thawed, not a replacement.
- **Check `ATEOM POD`** (`kubectl ate get actors --atespace agents`) - the
  actor may have landed on a different worker than before. The bash loop,
  mid-`sleep`, moved pods and never noticed.

This is the difference between Substrate and a scale-to-zero autoscaler: a
Deployment scaled back up starts a *new* container from scratch. Substrate
resumed a *checkpointed process* - for a real coding agent, that's an
in-flight session, loaded context, and working memory surviving the trip
through object storage.

---

## Step 6 - Optional: the dashboard

The demo ships a small Go dashboard that renders workers, actors, and pod
logs from the `ateapi` gRPC service. In one terminal, port-forward the API;
in another, run the UI:

```bash
# Terminal 1
kubectl port-forward svc/api 8080:443 -n ate-system

# Terminal 2 (from the Substrate repo root)
cd demos/claude-code-multiplex/ui
PORT=8090 ATEAPI_ADDR=localhost:8080 go run .
```

Open `http://localhost:8090`. The pods and agents panels are live cluster
state (via `ListWorkers` / `ListActors`); the logs pane reads real pod logs
via `client-go`.

> **Honesty note for the stage:** the "Give a task" button's
> queued → running → completed badges are client-side timers in the UI, not
> Substrate task states (Substrate has no per-task concept - see
> `ui/server.go`'s `computeState`). Use the badges as narrative, but point
> the audience at the actor status column and the logs pane for the real
> signals.

---

## Cleanup

Actors must be suspended before deletion; suspends of already-suspended
actors return immediately, so this is safe to run as-is:

```bash
for a in luna mars orion; do
  kubectl ate suspend actor "$a" --atespace agents 2>/dev/null
  kubectl ate delete actor "$a" --atespace agents
done
kubectl ate delete atespace agents
```

Remove the demo resources (namespace, Secret, WorkerPool, templates):

```bash
./hack/install-ate.sh --delete-demo-claude-code-multiplex
```

The Substrate control plane and cluster are untouched - tear those down via
the main [setup lab](../setup.md) if you're done with them. The workload
image remains in your registry; delete it there if you want it gone. Unset
the key from your shell when finished: `unset ANTHROPIC_API_KEY`.

---

## Troubleshooting

- **`no free workers available` on resume** - expected whenever both slots
  are held (Step 4). `kubectl ate get workers` shows who's holding them;
  suspend one and retry.
- **Deploy fails asking for `ANTHROPIC_API_KEY` / `BUCKET_NAME` /
  `KO_DOCKER_REPO`** - the install script hard-requires all three in the
  environment. Re-source `.ate-dev-env.sh` and re-export the key.
- **`docker buildx` push fails** - your Docker credential helper isn't
  configured for the registry. Re-run
  `gcloud auth configure-docker gcr.io` (or your Artifact Registry host).
- **Templates never go `Ready`** - same failure modes as the counter demo:
  check `kubectl describe actortemplate -n claude-multiplex-demo` and the
  `atelet` logs; usually bucket IAM or image pull (see the main lab's
  [troubleshooting](../setup.md#troubleshooting)).
- **Agent logs show Claude auth errors** - the key in the `anthropic-api-key`
  Secret is wrong or was exported with whitespace. Fix the export and
  re-run the deploy (it re-renders the Secret).
- **Logs are empty right after resume** - `kubectl ate logs` reads the
  current worker pod's logs; give the freshly resumed actor a few seconds to
  produce its first post-thaw tick.
- **Upstream context** - this demo carries runtime workarounds for two open
  Substrate issues (`#189` atelet OCI bundle gaps, `#197` symlink
  resolution); see `demos/claude-code-multiplex/README.md` if behavior looks
  odd after an upstream update.

---

## Recap

| Beat | What was proven |
|---|---|
| 3 actors created, 0 pods consumed | Suspended agents are free: they exist as records + snapshots, not containers. |
| 3 agents did real Claude work on 2 pods | Oversubscription works because agents are idle most of the time - the pool serves whoever is awake. |
| Third resume refused, then succeeded after a suspend | Capacity is an honest, visible signal - and freeing a slot is exactly what idle-suspension automates. |
| Tick counter continued across suspend/resume | Full-state checkpointing froze and thawed a live process - memory, loop variable, and all - possibly onto a different pod. |

The talk line: **"Two pods. Three agents. Nobody noticed - least of all the
agents."**
