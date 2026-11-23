# Manufacturing Agent Workshop

A Korean, browser-first practical workshop: company documents → process information → assembly video → a worker question → decisions → reports.

Start with [한국어 실행 안내](README.ko.md).

**[Open the workshop](https://darklightened.github.io/manufacturing-ai-agent-workshop/)** · **[Download materials](https://darklightened.github.io/manufacturing-ai-agent-workshop/downloads.html)**. No sign-in, Python installation or API key is required for the online lessons. Progress stays in your browser; export it before changing computers.

[Teaching materials](downloads.html): presentation slides (HTML/PDF/PowerPoint), example SOPs, drawing PDFs, criteria CSVs and sample inspection reports.

The default electronics lesson is a clearly labeled **authored teaching demo** with real public footage. Example observations and questions are written for an understandable classroom story, not presented as actual model predictions. PDF extraction, SQLite compilation, worker-answer handling, rule-dependent decisions and report generation are functional. No model/API/GPU calls occur during playback. A second authored measurement lesson selects a fictional product, loads its drawing and tolerances, accepts inspector/lot metadata and typed A/B readings, asks for one unclear value, and produces an inspection sheet. Product/drawing/specimen identities, raw readings and worker-confirmed numbers remain distinct. A third authored assembly lesson plays four stages of real public video, asks about one occluded pin, gates progression and saves photographic reports. The final document library keeps downloaded reports and inspection data locally and provides sample reports. Workers may optionally ask about the next assembly step; procedural guidance is recorded separately from inspection evidence. Earlier recorded-model and fixture paths are retained as instructor references.

```sh
python scripts/serve.py
```

Open `http://127.0.0.1:8921/` from the complete workshop pack. See [deployment](docs/DEPLOYMENT.ko.md) for separate source/media delivery.

```sh
node --test tests/*.test.mjs
python scripts/build.py
python scripts/package.py
```

These commands create local static and ZIP candidates. They do not publish a website.
