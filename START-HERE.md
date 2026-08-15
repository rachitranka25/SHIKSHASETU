# Start here

This runs an AI tutor for NCERT textbooks on your own computer. You do not need
to know how it works to run it.

You will need about **45 minutes**, most of which is waiting for downloads, and
roughly **20 GB of free disk space**.

---

## What you should have received

1. This project, from GitHub
2. A file called **`shiksha_setu.dump`** — about 213 MB
3. A **key** that looks like `nvapi-...`

If you are missing any of them, ask before starting.

---

## Step 1 — Install two things

**Python 3.11** — https://www.python.org/downloads/release/python-3119/

> When the installer opens, tick the box at the bottom that says
> **"Add python.exe to PATH"** before clicking Install. This matters.
> Do not install 3.12 or 3.13. They will not work.

**Docker Desktop** — https://www.docker.com/products/docker-desktop/

> After installing, open it. Wait until the whale icon at the bottom stops
> moving. Leave it running.

If you also want the website (not just the API), install **Node.js 20** from
https://nodejs.org/ — but you can skip it for now.

---

## Step 2 — Get the project

Install Git from https://git-scm.com/downloads if you do not have it, then open
**PowerShell** (press Start, type `powershell`, hit Enter) and paste:

```powershell
cd ~/Desktop
git clone https://github.com/rachitranka25/SHIKSHASETU.git
cd SHIKSHASETU
```

---

## Step 3 — Put the dump file in place

Copy **`shiksha_setu.dump`** into the folder that was just created
(`Desktop\SHIKSHASETU`). It must sit next to the file called `setup.ps1`.

This file is the textbooks, already processed. Without it the tutor starts but
cannot answer anything, and creating it yourself takes about six hours.

---

## Step 4 — Run the setup

In the same PowerShell window:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

It will print what it is doing. It takes 10 to 20 minutes, mostly installing.
If it stops with a red **STOP**, read that message — it says what is missing and
how to fix it. Fix it and run the same command again. Running it twice is safe.

---

## Step 5 — Add the key

Open the file called **`.env`** in the project folder with Notepad. Find the
line starting `NVIDIA_API_KEY=` and paste the key after the `=`, like this:

```
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxx
```

Save and close.

> Keep this key private. It is attached to somebody's account, and anyone who
> has it can spend on it. Do not put it in a screenshot, a message, or online.

---

## Step 6 — Start it

Open **two** PowerShell windows, both in the project folder.

In the first:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In the second:

```powershell
cd frontend
npm run dev
```

Then open **http://localhost:3000** in your browser.

**The first question will take a few minutes.** It is downloading about 2.3 GB
of the language model in the background. This happens once. Every question
afterwards takes about a second.

To stop, press `Ctrl+C` in both windows.

---

## If something goes wrong

**"docker: command not found" or "Docker is not running"**
Open Docker Desktop and wait for the whale icon to stop moving.

**"Python 3.11 was not found"**
You either installed a different version, or missed the *Add python.exe to
PATH* box. Reinstall 3.11 with that box ticked.

**"cannot be loaded because running scripts is disabled"**
Use the full command from Step 4, including `-ExecutionPolicy Bypass`.

**The page loads but every answer says something failed**
The key in `.env` is missing or wrong. Check Step 5.

**It answers, but the answers are not from the textbooks**
The dump did not load. Run this and see whether it prints a number near 155:

```powershell
docker compose exec postgres psql -U postgres -d shiksha_setu -tAc "SELECT count(DISTINCT metadata->>'book_code') FROM processed_content WHERE metadata->>'source'='NCERT';"
```

If it prints 0, the dump file was not in the folder when you ran setup. Put it
there and run setup again.

**Anything else**
Copy the whole red error message and send it to whoever gave you this. The
message usually contains the answer.
