(function (global) {
  "use strict";

  const sounds = {
    start: ["/static/audio/buddy/start-1.mp3", "/static/audio/buddy/start-2.mp3"],
    break: ["/static/audio/buddy/break-1.mp3"],
    celebration: [
      "/static/audio/buddy/celebration-1.mp3",
      "/static/audio/buddy/celebration-2.mp3",
      "/static/audio/buddy/celebration-3.mp3"
    ]
  };

  const config = { enabled: true, volume: 1 };
  let player = null;
  const lastChoice = {};

  function choose(type) {
    const choices = sounds[type] || [];
    if (!choices.length) return null;
    let index = Math.floor(Math.random() * choices.length);
    if (choices.length > 1 && index === lastChoice[type]) index = (index + 1) % choices.length;
    lastChoice[type] = index;
    return choices[index];
  }

  function stop() {
    if (!player) return;
    player.pause();
    player.currentTime = 0;
    player = null;
  }

  function play(type) {
    const source = choose(type);
    if (!config.enabled || !source) return false;
    stop();
    player = new Audio(source);
    player.preload = "auto";
    player.volume = Math.min(1, Math.max(0, Number(config.volume)));
    player.play().catch(() => {});
    return true;
  }

  global.addEventListener("pointerdown", () => {
    const audio = new Audio(sounds.start[0]);
    audio.muted = true;
    audio.play().then(() => { audio.pause(); audio.currentTime = 0; }).catch(() => {});
  }, { once: true });

  const api = {
    start: () => play("start"),
    takeBreak: () => play("break"),
    celebrate: () => play("celebration"),
    stop,
    configure(options) { Object.assign(config, options || {}); return { ...config }; },
    getConfig: () => ({ ...config })
  };

  global.StudyQuestBuddyVoice = api;
  global.buddyStart = api.start;
  global.buddyBreak = api.takeBreak;
  global.buddyCelebrate = api.celebrate;
})(window);
