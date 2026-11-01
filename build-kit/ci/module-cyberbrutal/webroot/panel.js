(function () {
  "use strict";
  var CONTROL = "/data/adb/modules/synthetica21_control/bin/synthetica-control.sh";
  var commands = ["profile_daily", "profile_gaming", "profile_revert"];
  var logEl = document.getElementById("log");
  var verdict = document.getElementById("verdict");
  var buttons = document.querySelectorAll("[data-cmd]");
  var busy = false;
  var bridgeReady = false;

  function log(message) {
    var prefix = new Date().toLocaleTimeString();
    logEl.textContent = "[" + prefix + "] " + message + "\n" + logEl.textContent;
  }

  function setButtons() {
    buttons.forEach(function (button) { button.disabled = busy || !bridgeReady; });
  }

  // KernelSU-Next UAPI-v4 WebUI supports exec(cmd, options, callbackName).
  // Do not infer success from the synchronous overload: it does not return an exit code.
  function exec(command, callback) {
    if (!window.ksu || typeof window.ksu.exec !== "function") {
      callback(1, "", "WebUI bridge unavailable; open this module in the Manager.");
      return;
    }
    var name = "__synthetica_cb_" + Math.random().toString(36).slice(2);
    var finished = false;
    var timer = window.setTimeout(function () {
      if (!finished) {
        finished = true;
        delete window[name];
        callback(1, "", "Root bridge timed out; result is unknown.");
      }
    }, 15000);
    window[name] = function (code, out, err) {
      if (finished) return;
      finished = true;
      window.clearTimeout(timer);
      delete window[name];
      callback(Number(code), String(out || ""), String(err || ""));
    };
    try { window.ksu.exec(command, null, name); }
    catch (e) {
      if (!finished) {
        finished = true;
        window.clearTimeout(timer);
        delete window[name];
        callback(1, "", String(e));
      }
    }
  }

  function telemetry() {
    var probe = [
      "printf 'GOV=%s\\n' \"$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor 2>/dev/null || echo --)\"",
      "printf 'CPU=%s\\n' \"$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq 2>/dev/null || echo --)\"",
      "printf 'GPU=%s\\n' \"$(cat /sys/class/kgsl/kgsl-3d0/min_pwrlevel 2>/dev/null || echo --)\"",
      "printf 'TEMP=%s\\n' \"$(cat /sys/class/power_supply/battery/temp 2>/dev/null || echo --)\"",
      "printf 'SWAP=%s\\n' \"$(cat /proc/sys/vm/swappiness 2>/dev/null || echo --)\"",
      "printf 'ZRAM=%s\\n' \"$(cat /sys/block/zram0/disksize 2>/dev/null || echo --)\""
    ].join("; ");
    exec(probe, function (code, out, err) {
      if (code !== 0) { log("Telemetry unavailable: " + (err || "root command failed")); return; }
      var values = {};
      out.split("\n").forEach(function (line) {
        var at = line.indexOf("=");
        if (at > 0) values[line.slice(0, at)] = line.slice(at + 1).trim();
      });
      [["GOV", "t-gov"], ["CPU", "t-cpu"], ["GPU", "t-gpu"], ["TEMP", "t-temp"],
       ["SWAP", "t-swap"], ["ZRAM", "t-zram"]].forEach(function (item) {
        document.getElementById(item[1]).textContent = values[item[0]] || "--";
      });
    });
  }

  function run(action) {
    if (busy || !bridgeReady || commands.indexOf(action) < 0) return;
    busy = true;
    setButtons();
    log("Running " + action + "...");
    exec("sh " + CONTROL + " " + action, function (code, out, err) {
      busy = false;
      setButtons();
      log((code === 0 ? "VERIFIED" : "PARTIAL / FAILED") + "\n" + (out || err || "No output"));
      telemetry();
    });
  }

  document.getElementById("themeBtn").addEventListener("click", function () { document.body.classList.toggle("light"); });
  document.getElementById("refresh").addEventListener("click", telemetry);
  buttons.forEach(function (button) { button.addEventListener("click", function () { run(button.getAttribute("data-cmd")); }); });
  exec("uname -r", function (code, out, err) {
    if (code !== 0 || !out.trim()) {
      verdict.className = "verdict bad";
      verdict.textContent = "ROOT BRIDGE UNAVAILABLE";
      log(err || "Unable to read kernel version.");
      return;
    }
    bridgeReady = true;
    verdict.className = "verdict ok";
    verdict.textContent = out.trim() + " // UNVERIFIED";
    setButtons();
    telemetry();
  });
})();
