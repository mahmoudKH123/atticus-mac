"""JARVIS mode: persona is opt-in, small, and leaves the upstream prompt untouched when off."""
import os
import unittest
from unittest.mock import patch

import atticus


def prompt(**prefs):
    with patch.object(atticus, 'pref', side_effect=lambda k, d: prefs.get(k, d)):
        return atticus.system_prompt(atticus.ASK_FIRST)


class JarvisTests(unittest.TestCase):
    def test_off_by_default_and_prompt_unchanged(self):
        self.assertNotIn('JARVIS', prompt())
        self.assertEqual(prompt(jarvis=False), prompt())
        self.assertEqual(prompt(jarvis=True), prompt() + atticus.JARVIS)

    def test_persona_is_small_and_keeps_safety(self):
        self.assertLessEqual(len(atticus.JARVIS), 2500)   # every ask pays for it
        for text in ('sir', 'Shall I go ahead?', 'Allow card', 'Cairo', 'never quote films'):
            self.assertIn(text, atticus.JARVIS)

    def test_speech_drops_comma_before_sir_only_in_jarvis_mode(self):
        source = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        self.assertIn('if Prefs.bool("jarvis"), let words = arguments.popLast() { arguments.append(jarvisSpoken(words)) }', source)
        self.assertIn('words.replacingOccurrences(of: #",\\s+(sir|Sir)\\b"#, with: " $1"', source)

    def test_voice_path_is_jarvis_only_and_settings_exist(self):
        source = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        deliver = source[source.index("    func deliver("):source.index("    func linger(")]
        self.assertIn('p.executableURL = URL(fileURLWithPath: "/usr/bin/say"); p.arguments = arguments', deliver)   # upstream path unchanged
        self.assertIn('if Prefs.bool("jarvis"), let words = arguments.last, let me = Bundle.main.executableURL { p.executableURL = me; p.arguments = ["--jarvis-say", words] }', deliver)
        for default in ('"jarvis": false', '"jarvisVoice": "Daniel (Enhanced)"', '"jarvisRate": 180', '"jarvisPitch": 0', '"jarvisEffect": false', '"jarvisEngine": "kokoro"', '"jarvisKokoroVoice": "bm_daniel"'):
            self.assertIn(default, source)
        page = open(os.path.join(os.path.dirname(__file__), '..', 'ui', 'settings.html')).read()
        for key in ('data-k="jarvis"', 'data-k="jarvisRate"', 'data-k="jarvisPitch"', 'data-k="jarvisEffect"', 'data-k="jarvisEngine"', 'id="jarvisTest"'):
            self.assertIn(key, page)

    def test_kokoro_falls_back_to_apple_voice(self):
        source = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        helper = source[source.index('if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--jarvis-say"'):]
        self.assertIn('if jarvisKokoroReady(), jarvisKokoroSpeak(words, rate: rate, into: out) { return true }', helper)
        self.assertIn('// Apple\'s voice: always installed, works offline', helper)
        self.assertIn('stop.setEventHandler { jarvisRenderer?.terminate()', helper)

    def test_kokoro_service_is_private_and_self_stopping(self):
        source = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        server = source[source.index('let jarvisKokoroServer = """'):source.index('// Runs a renderer')]
        self.assertIn("os.umask(0o177)", server)                     # socket readable by this user only
        self.assertIn("fcntl.LOCK_EX | fcntl.LOCK_NB", server)       # never two copies
        self.assertIn("except ProcessLookupError: os._exit(0)", server)   # quits with Atticus
        self.assertIn("if not p.get('jarvis') or p.get('jarvisEngine', 'kokoro') != 'kokoro': os._exit(0)", server)
        self.assertIn('if Prefs.bool("jarvis") { jarvisWarm() }', source)


    def test_hands_free_stays_on_until_sign_off_only_in_jarvis_mode(self):
        source = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        self.assertIn('held > ((quietFollowUp || handsFree && picking) && Prefs.bool("jarvis") ? 50 : 8)', source)              # silence no longer closes the mic
        self.assertIn('if quietFollowUp && Prefs.bool("jarvis") { hush(); followUp = true; return wakeTick() }; if quietFollowUp { hush(); fadeIdleHandsFree(); return }; if offerText != nil { stopOfferInput(); jarvisCardListen(); return };', source)
        self.assertIn('if handsFree, offerText == nil, Prefs.bool("jarvis"), Self.endsJarvisChat(text) { cue("soundStop"); close(clear: false); return }', source)
        self.assertIn("if handsFree { close(clear: false); return }", source)                           # Esc still ends it


    def test_voice_starts_on_first_sentence_only_in_jarvis_mode(self):
        said = []
        with patch.object(atticus, 'say', side_effect=lambda tag, text: said.append((tag, text))):
            text, voiced = 'Evening, Mahmoud. Battery is at 3.5 per cent! Want me to', 0
            for i in range(1, len(text) + 1): voiced = atticus.voice_sentences(text[:i], voiced)
            self.assertEqual(said, [('♪', 'Evening, Mahmoud.'), ('♪', 'Battery is at 3.5 per cent!')])
            self.assertEqual(text[voiced:], ' Want me to')                       # the unfinished sentence waits for the final answer
            said.clear(); self.assertEqual(atticus.voice_sentences('[draft] Hi there. Bye ', 0), 0); self.assertEqual(said, [])
        source = open(atticus.__file__).read()
        self.assertIn("voices, voiced = os.environ.get('ATTICUS_UI') == '1' and pref('jarvis', False) and pref('speak', False), 0", source)
        self.assertIn("if voices and not drew and (not commit or os.path.exists(commit)): voiced = voice_sentences(live, voiced)", source)   # never before the words are confirmed
        self.assertIn("if not commit or os.path.exists(commit): voiced = voice_sentences(live + ' ', voiced)", source)   # last sentence on text end, not ~2 s later at the result
        app = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        self.assertIn('if line.hasPrefix("♪ ") { self.jarvisSpeakLive(String(line.dropFirst(2))); continue }', app)
        self.assertIn('guard Prefs.bool("jarvis"), Prefs.bool("speak"), let me = Bundle.main.executableURL else { return }', app)
        self.assertIn('self.jarvisEndLive()   // a reply that ended without a final answer', app)


    def test_choices_card_is_asked_aloud_and_answered_by_voice_in_jarvis_hands_free(self):
        app = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        self.assertIn('DispatchQueue.main.async { [weak self] in self?.jarvisAskCard(j["q"] as? String ?? "") }', app)
        self.assertIn('guard Prefs.bool("jarvis"), picking || jarvisApproval && retryOffer && !askFile.isEmpty, !engine.isRunning else { return }', app)   # JARVIS mode only: a choices card or a spoken approval


    def test_ai_sign_off_ends_hands_free_chat_only_in_jarvis_mode(self):
        self.assertIn('end with [bye]', atticus.JARVIS)
        source = open(atticus.__file__).read()
        self.assertIn("bye = pref('jarvis', False) and '[bye]' in reply", source)
        self.assertIn("if bye: reply = reply.replace('[bye]', '').strip()", source)               # never shown or spoken
        self.assertIn("if bye and os.environ.get('ATTICUS_UI') == '1': print('⏻', flush=True)", source)
        app = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        self.assertIn('if line == "⏻" { if Prefs.bool("jarvis") { self.handsFree = false; self.followUp = false }; continue }', app)


    def test_jarvis_sends_heard_words_without_waiting_for_punctuation(self):
        app = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        stop = app[app.index('    func stop() {', app.index('final class App')):]
        stop = stop[:stop.index('Task {   // let the model finish the last words, then act')]
        self.assertIn('if Prefs.bool("jarvis") && !dictating && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {', stop)   # dictation keeps the final pass
        self.assertIn('rd?.cancel(); Task { await an?.cancelAndFinishNow() }', stop)   # late words from the old listen are dropped
        self.assertIn('return once(true)', stop)


    def test_double_clap_wakes_only_in_jarvis_mode_and_is_off_by_default(self):
        app = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        self.assertIn('"jarvisClap": false', app)
        self.assertIn('var clapOn: Bool { Prefs.bool("jarvis") && Prefs.bool("jarvisClap") }', app)
        self.assertIn('("off", !Prefs.bool("wakeWord") && !clapOn)', app)
        self.assertIn('guard Prefs.bool("wakeWord") else { if wakeRequest != nil { stopWake() }; return }', app)   # clap only: no word listener
        self.assertIn('wakeMic.start(device, sampleRate: 16000, { request.append($0) })', app)                   # word listener unchanged
        self.assertIn('clapMic.start(device, sampleRate: 16000, { detector.feed($0) })', app)                    # claps on their own steady mic
        self.assertIn('stopClap(); if wakeRequest != nil { stopWake() }; return', app)                          # off while busy, talking, speaking, in a meeting
        self.assertIn('if at < ignoreUntil || claps.count == 2 && at < quietUntil { claps = []; ignoreUntil = at + 1; return }', app)   # applause never wakes
        page = open(os.path.join(os.path.dirname(__file__), '..', 'ui', 'settings.html')).read()
        self.assertIn('data-k="jarvisClap"', page)


    def test_face_is_jarvis_only_full_screen_click_through_and_shows_no_text(self):
        app = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        face = app[app.index('final class JarvisFace'):app.index('func jarvisWarm()')]
        self.assertIn('p.ignoresMouseEvents = true', face)                         # clicks pass through
        self.assertIn('p.setFrame(screen.frame, display: true)', face)             # the whole screen, menu bar and Dock included
        self.assertIn('["legion", "lenovo"]', face)                                 # the Lenovo when it's connected
        self.assertIn('CGDisplayIsBuiltin', face)                                   # else this Mac's own screen
        self.assertIn('applySharing(p)', face)
        self.assertIn('let on = Prefs.bool("jarvis")', app)
        self.assertIn('if on && !dictating && (handsFree || busy || engine.isRunning || speaking) {', app)
        show = app[app.index('    func show() {'):app.index('    func hide(after s: Double) {')]
        self.assertIn('if Prefs.bool("jarvis") && !dictating {', show)               # no box in JARVIS mode; dictation keeps its pill
        self.assertIn('Timer.scheduledTimer(withTimeInterval: 1.0 / 30, repeats: true) { _ in app.jarvisTick() }', app)
        page = open(os.path.join(os.path.dirname(__file__), '..', 'ui', 'jarvis.html')).read()
        for api in ('wake()', 'sleep()', 'state(s)', 'level(v)'):
            self.assertIn(api, page)
        self.assertNotIn('simulate(', page)                                        # the preview's demo loop is not shipped
        self.assertIn("if (phase === 'off' && flash < 0.01) { running = false;", page)   # draws nothing while asleep

    def test_voice_level_only_when_the_app_asks(self):
        app = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        self.assertIn('if ProcessInfo.processInfo.environment["ATTICUS_JARVIS_LEVELS"] == "1" {', app)
        self.assertIn('env["ATTICUS_JARVIS_LEVELS"] = "1"; p.environment = env', app)
        self.assertIn('if Prefs.bool("jarvis") { jarvisLevels(p) }', app)

    def test_approvals_are_spoken_and_answered_by_voice_in_jarvis_mode(self):
        app = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
        self.assertIn('DispatchQueue.main.async { [weak self] in self?.jarvisAskApproval(p[0]) }', app)
        self.assertIn('guard Prefs.bool("jarvis"), !retryOffer, !askFile.isEmpty else { return }', app)
        self.assertIn('if let ok = Self.jarvisYesNo(heard) { jarvisApproval = false; retryOffer = false; allow(ok) }', app)
        self.assertIn('else { jarvisSpeakLive("Sorry, yes or no?"); jarvisEndLive(); jarvisCardListen() }', app)   # unclear: ask again, never guess


if __name__ == '__main__':
    unittest.main()
