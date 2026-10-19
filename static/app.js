// AI Fringe Report: field hum audio and share buttons. No network calls.
(() => {
  // ---- share: native share sheet on phones, copy link elsewhere ----
  document.querySelectorAll("button.share").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const url = btn.dataset.shareUrl, title = btn.dataset.shareTitle;
      try {
        if (navigator.share) {
          await navigator.share({ title, url });
          return;
        }
        await navigator.clipboard.writeText(url);
        btn.textContent = "Link copied";
      } catch (err) {
        if (err && err.name === "AbortError") return; // person closed the share sheet
        window.prompt("Copy this link:", url);
      }
      setTimeout(() => { btn.textContent = "Share"; }, 2500);
    });
  });

  // ---- field hum: low drone with occasional crystalline pings ----
  const hum = document.getElementById("hum");
  if (!hum) return;
  let ctx = null, timer = null;
  const pings = [523.3, 587.3, 659.3, 784.0, 880.0, 1046.5];
  function start() {
    ctx = new AudioContext();
    const master = ctx.createGain();
    master.gain.value = 0.07;
    master.connect(ctx.destination);
    [55, 82.4].forEach((freq, i) => {
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      const lfo = ctx.createOscillator(), depth = ctx.createGain();
      osc.frequency.value = freq; gain.gain.value = 0.5;
      lfo.frequency.value = 0.07 + i * 0.04; depth.gain.value = 0.25;
      lfo.connect(depth); depth.connect(gain.gain);
      osc.connect(gain); gain.connect(master); osc.start(); lfo.start();
    });
    timer = setInterval(() => {
      if (Math.random() < 0.45) return;
      const osc = ctx.createOscillator(), gain = ctx.createGain(), now = ctx.currentTime;
      osc.frequency.value = pings[Math.floor(Math.random() * pings.length)];
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(0.12, now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 2.4);
      osc.connect(gain); gain.connect(master); osc.start(now); osc.stop(now + 2.5);
    }, 900);
    hum.textContent = "Stop field hum";
    hum.setAttribute("aria-pressed", "true");
  }
  function stop() {
    clearInterval(timer); ctx.close(); ctx = null;
    hum.textContent = "Play field hum";
    hum.setAttribute("aria-pressed", "false");
  }
  hum.addEventListener("click", () => (ctx ? stop() : start()));
})();
