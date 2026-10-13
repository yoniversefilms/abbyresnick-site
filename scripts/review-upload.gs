/**
 * Google Apps Script — receives voice notes from abbyresnick.com/review and saves them in Drive.
 *
 * One-time setup (Yonatan, ~3 minutes):
 *   1. script.google.com → New project → paste this file → save (name it "Abby site notes").
 *   2. Deploy → New deployment → type "Web app" → Execute as: Me · Who has access: Anyone → Deploy.
 *      Approve the Drive permission when asked.
 *   3. Copy the Web app URL (https://script.google.com/macros/s/…/exec) into UPLOAD_URL in review/index.html.
 *
 * Every note lands in the Drive folder "Abby site notes" as abby-notes-NN-<page>-<date>-<time>.m4a (or .webm),
 * with the page(s), start time and duration in the file description. Claude reads that folder through the
 * Google Drive connector.
 */
var FOLDER_NAME = 'Abby site notes';

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    if (!body || !body.data || !body.name) return json_({ ok: false, error: 'missing data' });
    var name = String(body.name).replace(/[^a-z0-9._-]/gi, '-').slice(0, 120);
    var blob = Utilities.newBlob(Utilities.base64Decode(body.data), body.mime || 'audio/mp4', name);
    var file = folder_().createFile(blob);
    file.setDescription(JSON.stringify({
      pages: body.pages || [body.page], startedAt: body.startedAt, durationMs: body.durationMs, size: body.size,
      receivedAt: new Date().toISOString()
    }));
    return json_({ ok: true, id: file.getId(), name: file.getName() });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doGet() { return json_({ ok: true, service: 'abby-review-upload' }); }

function folder_() {
  var it = DriveApp.getFoldersByName(FOLDER_NAME);
  return it.hasNext() ? it.next() : DriveApp.createFolder(FOLDER_NAME);
}
function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
