import { Capacitor } from '@capacitor/core';
import { Browser } from '@capacitor/browser';
import { LocalNotifications } from '@capacitor/local-notifications';

const $ = id => document.getElementById(id);
const REMINDER_ID = 7301;
const DEFAULT_URL = 'https://study-quest-2t6s.onrender.com/';
const storedUrl = localStorage.getItem('sq_server_url');
if (storedUrl) $('server').value = storedUrl;

function say(id, message, good = false) {
  const node = $(id);
  node.textContent = message;
  node.classList.toggle('good', good);
}
const savedTheme = localStorage.getItem('sq_mobile_theme') || 'dark';
document.documentElement.dataset.theme = savedTheme;
$('themeToggle').textContent = savedTheme === 'dark' ? '☼' : '☾';
$('themeToggle').addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('sq_mobile_theme', next);
  $('themeToggle').textContent = next === 'dark' ? '☼' : '☾';
});
$('open').addEventListener('click', async () => {
  let url;
  try { url = new URL($('server').value.trim()); }
  catch { say('status', 'Enter a complete website address beginning with https://'); return; }
  if (url.protocol !== 'https:' || url.hostname !== 'study-quest-2t6s.onrender.com') {
    say('status', 'For safety, use the official Study Quest HTTPS address.'); return;
  }
  localStorage.setItem('sq_server_url', url.href);
  try {
    if (Capacitor.isNativePlatform()) await Browser.open({ url: url.href });
    else window.open(url.href, '_blank', 'noopener,noreferrer');
    say('status', 'Opening your Study Quest website…', true);
  } catch (error) { say('status', 'Could not open Study Quest: ' + (error?.message || 'unknown error')); }
});
$('schedule').addEventListener('click', async () => {
  try {
    if (!Capacitor.isNativePlatform()) { say('noticeStatus', 'Native reminders are available after installing the Android app.'); return; }
    const time = $('reminderTime').value;
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) { say('noticeStatus', 'Choose a valid reminder time.'); return; }
    let permission = await LocalNotifications.checkPermissions();
    if (permission.display !== 'granted') permission = await LocalNotifications.requestPermissions();
    if (permission.display !== 'granted') { say('noticeStatus', 'Allow notifications for Study Quest in Android Settings.'); return; }
    const [hour, minute] = time.split(':').map(Number);
    await LocalNotifications.cancel({ notifications: [{ id: REMINDER_ID }] });
    await LocalNotifications.schedule({ notifications: [{
      id: REMINDER_ID,
      title: 'Study Quest 🐰',
      body: 'Your syllabus isn’t going to finish itself. Ready for today’s quest?',
      schedule: { on: { hour, minute }, repeats: true, allowWhileIdle: true },
      smallIcon: 'ic_stat_icon_config_sample',
      iconColor: '#FF5A00'
    }] });
    localStorage.setItem('sq_reminder_time', time);
    say('noticeStatus', 'Daily reminder enabled for ' + time + '.', true);
  } catch (error) { say('noticeStatus', 'Could not schedule reminder: ' + (error?.message || 'unknown error')); }
});
$('cancel').addEventListener('click', async () => {
  try {
    if (!Capacitor.isNativePlatform()) { say('noticeStatus', 'Install the Android build to manage native reminders.'); return; }
    await LocalNotifications.cancel({ notifications: [{ id: REMINDER_ID }] });
    localStorage.removeItem('sq_reminder_time');
    say('noticeStatus', 'Daily reminder cancelled.', true);
  } catch (error) { say('noticeStatus', 'Could not cancel reminder: ' + (error?.message || 'unknown error')); }
});
const savedTime = localStorage.getItem('sq_reminder_time');
if (savedTime) $('reminderTime').value = savedTime;