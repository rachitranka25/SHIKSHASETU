# STATUS — 11 August 2026, 15:54 IST

Terminal ka rendering toot gaya, isliye ye file likhi hai. Cursor mein khul rahi hai,
toh yahan sab kuch hai.

---

## Terminal theek karne ka tareeka

Terminal panel mein type karo (dikhega nahi, par chalega):

```
reset
```

Enter dabao. Agar phir bhi na sudhre:

1. Cursor mein terminal panel band karo aur naya kholo — `Ctrl+`` ` (backtick)
2. Ya Cursor restart karo

Ye project ka problem nahi hai — terminal ka escape-sequence state kharab hua hai,
shayad reboot ke baad. Data ya kaam kuch nahi gaya.

---

## Ingestion — CHAL RAHI HAI, ~1 GHANTA BAAKI

| | |
|---|---|
| **Books ho gaye** | **135** |
| Chunks | 37,187 |
| Classes | **1 se 12, saari** |
| **Bache** | **28** — sab class 12 ki (`lehe1`, `lehs1`, `lelm1` ...) |
| **ETA** | **~1.1 ghanta** (140 s/book ke measured rate pe) |

Subah 30 books the. Ab 135.

**Khud check karne ke liye** (terminal theek hone ke baad):

```bash
cd "/Users/rachitranka/Desktop/projects zip/Shiksha-setu-main"
psql -d shiksha_setu -tAc "select count(distinct metadata->>'book_code') from processed_content where metadata->>'source'='NCERT';"
```

Live log:

```bash
tail -f data/logs/ingest_day3.log
```

---

## Aaj do cheezein toot ke theek hui

**1. Machine reboot ho gaya (13:13 pe).** Postgres aur ingestion dono mar gaye.
Postgres phir start nahi ho raha tha — unclean shutdown se stale `postmaster.pid`
bacha tha. Us file mein PID 989 likha tha aur PID 989 **zinda** tha, toh lagta tha
Postgres chal raha hai. Check kiya to wo **Brave Browser** nikla, jo boot ke baad
usi PID pe aa gaya. Lock file 28 July ka tha.

Lock ko delete nahi kiya — `postmaster.pid.stale-<timestamp>` naam se hata diya,
taaki galat nikalta to wapas mil jaata. Postgres restart hua, WAL replay ne **poora
data recover kiya**, kuch nahi khoya.

**2. Raat ko ek infinite retry loop chala.** 1,178 batches chale aur sirf 16 books
ingest hui. Wajah: book ek transaction mein commit hoti hai, toh fail hone pe poora
rollback ho jaata hai aur book DB mein nahi aati. Batch runner "jo DB mein nahi hai"
wahi chunta hai — toh **jo book pakka fail hoti hai, wo pakka dobara chuni jaati hai,
hamesha.**

Do tarah ki books aisi thi: class 5 Rimjhim (zip corrupt — `Bad CRC-32`), aur
legacy-font Hindi readers (saare chapters sahi tarah reject hote hain, toh 0 chapters
bachte hain). 404 pe marker pehle se lagta tha; in dono par kuch nahi lagta tha.

Fix: `record_dead_end()` ab dono ke liye marker likhta hai, reason file ke andar.
Commit `e84edf3`. Uske baad 75 → 128 books.

---

## Final count 263 nahi hoga — ye paper mein likhna padega

```
ho gaye            135 books
dead-end / 404     108 books
bache               28 books   ->  ~1 ghanta
                   ─────────
final banega      ~163 books   (263 nahi)
```

Wo 108 books: kuch ke zip NCERT ne publish hi nahi kiye, ek corrupt hai, aur kaafi
legacy-font Hindi readers hain. **Sab marked hain reason ke saath**, toh paper mein
exact likha ja sakta hai. Ye honest limitation hai — chhupane wali cheez nahi, aur
ek reviewer isse achha maanega.

---

## Paper — READY hai

```
docs/IEEE_PAPER_SHIKSHA_SETU.pdf
```

**7 pages · 14 tables · citations 1–21 contiguous · 0 broken refs · 0 overfull boxes
· Times with real bold + italic**

Audit ke saare 6 items done, plus 4 cheezein jo audit ne miss ki thi. Do sabse
important:

- **Audit ka #4 ulta tha.** "Table XIV ko 97 s/book karo" — maine controlled A/B
  chalaya (wahi 3 books, prefetch on/off, identical output): sequential **193 s/book**,
  prefetch **140 s/book**, 1.38x. Toh paper ka "3.1 min sequential" sahi tha; galat
  number 97 s/book tha. Audit maan lete to paper ek aisa improvement claim karta jo
  data ke ulta hai — reviewer reproduce karta to pakda jaata.

- **Bold/italic PDF mein bilkul nahi tha.** Sirf `LMRoman-Regular` embed thi — har
  `\textbf` aur `\textit` regular render ho raha tha, aur font Times bhi nahi thi.
  Wajah: `tgtermes` pdfTeX ka package hai, XeTeX mein chup-chaap fail hua, ek warning
  bhi nahi. `fontspec` se theek kiya: ab **3,321 bold + 1,358 italic** characters, aur
  Times narrower hone se pages 8 → 7 ho gaye.

---

## Ab kya karna hai

Ingestion ~1.5 ghante mein khatam. Uske baad mujhe bas itna bolna:

> **"ingestion done, paper update kar"**

Main:
1. Paper ke corpus numbers update karunga (abhi Section V-A mein 30 books / 9,722
   passages likha hai → final count)
2. Bade corpus pe cross-lingual evaluation **dobara** chalaunga — abhi 0.596–0.672
   sirf 30 books pe hai, 170 books pe wo zyada meaningful hoga
3. Naya PDF dunga

Agar terminal theek na ho, to bas is file ko refresh karke padh lena — main isse
update karta rahunga.
