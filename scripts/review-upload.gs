/**
 * Google Apps Script — receives voice notes from abbyresnick.com/review and saves them in Drive.
 *
 * One-time setup (Yonatan, ~3 minutes):
 *   1. script.google.com → New project → paste this file over the default code → save (name it "Abby site notes").
 *   2. Deploy → New deployment → gear icon → type "Web app"
 *        Execute as: Me
 *        Who has access: Anyone            ← not "Anyone with Google account" (Abby isn't signed in)
 *      → Deploy. On the "Google hasn't verified this app" screen: Advanced → Go to Abby site notes → Allow.
 *   3. Check it: open the Web app URL (…/exec) in a browser. It must show {"ok":true,"service":"abby-review-upload"}.
 *   4. Paste that URL into UPLOAD_URL in review/index.html and push.
 *   Later edits to this script: Deploy → Manage deployments → pencil → Version: New version → Deploy
 *   (that keeps the same URL; a fresh "New deployment" would change it).
 *
 * What it accepts: audio only, up to MAX_MB per note, into one Drive folder. The URL sits in public HTML,
 * so anyone could post audio to it — nothing else is reachable through it, and every file lands in that
 * one folder with a sanitised name. The same note posted twice (a retry after a lost reply) is kept once.
 *
 * Files: abby-note-<YYYY-MM-DD>-<HHMMSS>-<page>.m4a (or .webm), with pages visited, start time and duration
 * in the file description. Claude reads the folder through the Google Drive connector.
 */
var FOLDER_NAME = 'Abby site notes';
var MAX_MB = 40;

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    var body = JSON.parse(e.postData.contents);
    if (!body || !body.data || !body.name || !body.id) return json_({ ok: false, error: 'missing data' });
    var mime = String(body.mime || 'audio/mp4').split(';')[0].trim().toLowerCase();
    if (mime.indexOf('audio/') !== 0) return json_({ ok: false, error: 'audio only' });
    if (String(body.data).length > MAX_MB * 1024 * 1024 * 4 / 3) return json_({ ok: false, error: 'too large' });
    var name = String(body.name).replace(/[^a-z0-9._-]/gi, '-').slice(0, 120);
    var id = String(body.id).replace(/[^0-9a-z-]/gi, '').slice(0, 40);

    lock.waitLock(30000);
    var folder = folder_(), props = PropertiesService.getScriptProperties();
    var bytes = Utilities.base64Decode(body.data);
    var existing = findById_(folder, id, name, props);
    if (existing) {
      // A retry of a note already saved. Keep whichever copy is longer (a partial copy can arrive first).
      if (existing.getSize() >= bytes.length) return json_({ ok: true, id: existing.getId(), name: existing.getName(), duplicate: true });
      existing.setTrashed(true);
    }
    var file = folder.createFile(Utilities.newBlob(bytes, mime, name));
    props.setProperty('note:' + id, file.getId());
    file.setDescription(JSON.stringify({
      noteId: id, pages: body.pages || [body.page], startedAt: body.startedAt, durationMs: body.durationMs, size: body.size,
      receivedAt: new Date().toISOString()
    }));
    return json_({ ok: true, id: file.getId(), name: file.getName() });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    try { lock.releaseLock(); } catch (e2) {}
  }
}

function doGet() { return json_({ ok: true, service: 'abby-review-upload' }); }

/* One folder, remembered by id so two uploads starting together can't each create one. */
function folder_() {
  var props = PropertiesService.getScriptProperties(), id = props.getProperty('folderId');
  if (id) { try { return DriveApp.getFolderById(id); } catch (e) {} }
  var it = DriveApp.getFoldersByName(FOLDER_NAME);
  var folder = it.hasNext() ? it.next() : DriveApp.createFolder(FOLDER_NAME);
  props.setProperty('folderId', folder.getId());
  return folder;
}
/* Script properties are immediately consistent (Drive search is not); the deterministic name is the fallback. */
function findById_(folder, id, name, props) {
  var fileId = props.getProperty('note:' + id);
  if (fileId) { try { var f = DriveApp.getFileById(fileId); if (!f.isTrashed()) return f; } catch (e) {} }
  var files = folder.getFilesByName(name);
  while (files.hasNext()) { var g = files.next(); if (!g.isTrashed()) return g; }
  return null;
}
function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
