# pCloud API Methods Documentation

> **Source:** <https://docs.pcloud.com/methods>

## Overview

pCloud provides a RESTful API for accessing and managing cloud storage. All API calls consist of a method name and parameters.

### Important Notes

- pCloud has two data centers: **United States** (`api.pcloud.com`) and **Europe** (`eapi.pcloud.com`).
- API calls must target the correct hostname based on where the user registered.
- Files and folders can be accessed by full path *(discouraged)* or by `fileid`/`folderid`.
- The root folder always has `folderid` of `0`.
- Full paths always start with `/`. Trailing slashes MUST NOT be present.
- Implementations MUST accept 64-bit numbers for all IDs, quotas, and file sizes.

---

## Table of Contents

- [General](#general)
- [Folder](#folder)
- [File](#file)
- [Auth](#auth)
- [Streaming](#streaming)
- [Archiving](#archiving)
- [Sharing](#sharing)
- [Public Links](#public-links)
- [Thumbnails](#thumbnails)
- [Upload Links](#upload-links)
- [Revisions](#revisions)
- [Newsletter](#newsletter)
- [Trash](#trash)
- [Collection](#collection)
- [OAuth 2.0](#oauth-20)
- [Transfer](#transfer)

---

## General

### getdigest

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getdigest` |
| **Description** | Returns a digest for digest authentication. Digests are valid for 30 seconds. |

**Output:**

| Parameter | Description |
|---|---|
| `digest` | string — the digest for authentication |
| `expires` | datetime — when the digest expires |

**Errors:** `1000`, `2000`, `4000`

---

### userinfo

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/userinfo` |
| **Description** | Returns information about the current user. As there is no specific login method (credentials can be passed to any method), this is a good place for logging in with no particular action in mind. |

**Output:**

| Parameter | Description |
|---|---|
| `email` | string — email address of the user |
| `emailverified` | bool — true if the user has verified their email |
| `registered` | datetime — when the user registered |
| `premium` | bool — true if the user is premium |
| `premiumexpires` | datetime — if premium is true, the date until which the service is active |
| `quota` | int — quota in bytes |
| `usedquota` | int — used quota in bytes |
| `language` | string — 2–3 character lowercase language ID |

**Errors:** `1000`, `2000`, `4000`

---

### supportedlanguages

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/supportedlanguages` |
| **Description** | Lists supported languages in the returned `languages` hash, where keys are language codes and values are language names. |

**Errors:** `1000`, `2000`, `4000`

---

### setlanguage

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/setlanguage` |
| **Description** | Sets the user's language. |

**Required:**

| Parameter | Description |
|---|---|
| `language` | string — the language to be set |

**Errors:** `1000`, `1020`, `1021`, `2000`, `4000`, `5000`

---

### feedback

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/feedback` |
| **Description** | Sends a message to pCloud support. |

**Required:**

| Parameter | Description |
|---|---|
| `mail` | string — email of the user |
| `reason` | string — subject of the request |
| `message` | string — the message itself |

**Optional:**

| Parameter | Description |
|---|---|
| `name` | string — user's full name |

**Errors:** `1000`, `1033`, `1041`, `1042`, `2000`, `2018`, `4000`

---

### currentserver

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/currentserver` |
| **Description** | Returns IP and hostname of the server you are currently connected to. The hostname is guaranteed to resolve only to the IP address(es) pointing to the same server. Useful when tracking upload progress. |

**Output:**

| Parameter | Description |
|---|---|
| `ip` | string — IPv4 address |
| `ipbin` | string — IPv4 address |
| `ipv6` | string — IPv6 address |
| `hostname` | string — hostname of the server |

**Errors:** `1000`, `2000`, `4000`

---

### diff

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/diff` |
| **Description** | Lists updates of the user's folders/files. Optionally takes `diffid` to return only changes since that diffid. Can also use `after` (datetime) or `last` (int). Setting `last` to 0 is optimized to return only the last diffid. If `block` is set and there are no changes since the provided diffid, the connection will block until an event arrives. |

**Optional:**

| Parameter | Description |
|---|---|
| `diffid` | int — receive only changes since that diffid |
| `after` | datetime — receive only events generated after that time |
| `last` | int — return last N events with highest diffids |
| `block` | int — if set, connection blocks until an event arrives (works only with diffid) |
| `limit` | int — max entries to return |

**Output:**

Returns `entries` array and `diffid`. Each entry contains:

| Field | Description |
|---|---|
| `diffid` | int — the event's identifier |
| `time` | datetime — timestamp of the event |
| `event` | event type (see Event structure docs) |

In most cases, `metadata` is also provided.

**Errors:** `1000`, `1013`, `2000`, `4000`, `5000`

---

### getfilehistory

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getfilehistory` |
| **Description** | Returns event history of a file identified by `fileid`. The file may be deleted. Output format is the same as `diff`. |

**Required:**

| Parameter | Description |
|---|---|
| `fileid` | int — fileid of the file |

**Errors:** `1000`, `1029`, `2000`, `2009`, `4000`, `5000`

---

### getip

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getip` |
| **Description** | Returns the IP address and country of the remote device connecting to the API. |

**Output:**

| Parameter | Description |
|---|---|
| `ip` | string — remote address |
| `country` | string — lowercase two-letter country code, or `false` if unknown |

---

### getapiserver

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getapiserver` |
| **Description** | Returns the closest API server to the requesting client. Biggest speed gain is with upload methods. Clients should have fallback logic to `api.pcloud.com`. |

**Output:**

| Parameter | Description |
|---|---|
| `binapi` | array — API servers supporting pCloud's binary protocol |
| `api` | array — API servers supporting HTTP/HTTPS |

---

## Folder

### createfolder

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/createfolder` |
| **Description** | Creates a folder. Expects either `path` or `folderid` + `name`. |

**Required (use `path` OR `folderid` + `name`):**

| Parameter | Description |
|---|---|
| `path` | string — path to the folder (discouraged) |
| `folderid` | int — parent folder ID |
| `name` | string — name of the new folder |

**Output:** Returns metadata of the created folder.

**Errors:** `1000`, `1001`, `2000`, `2001`, `2002`, `2003`, `2004`, `4000`, `5000`

---

### createfolderifnotexists

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/createfolderifnotexists` |
| **Description** | Creates a folder if it doesn't exist, or returns the existing folder's metadata. |

**Required (use `path` OR `folderid` + `name`):**

| Parameter | Description |
|---|---|
| `path` | string — path to the folder (discouraged) |
| `folderid` | int — parent folder ID |
| `name` | string — name of the folder |

**Output:** Returns metadata. Also returns `created` (bool) indicating whether the folder was newly created.

**Errors:** `1000`, `1001`, `2000`, `2001`, `2002`, `2003`, `4000`, `5000`

---

### listfolder

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/listfolder` |
| **Description** | Returns data for a folder. The metadata will have a `contents` field that is an array of metadata for the folder's contents. Recursively listing the root folder is not an expensive operation. |

**Required (use `path` OR `folderid`):**

| Parameter | Description |
|---|---|
| `path` | string — path to the folder (discouraged) |
| `folderid` | int — ID of the folder |

**Optional:**

| Parameter | Description |
|---|---|
| `recursive` | int — if set, full directory tree is returned |
| `showdeleted` | int — if set, deleted files/folders that can be undeleted are displayed |
| `nofiles` | int — if set, only folder (sub)structure is returned |
| `noshares` | int — if set, only user's own folders and files are displayed |

**Errors:** `1000`, `1002`, `2000`, `2003`, `2005`, `4000`, `5000`

---

### renamefolder

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/renamefolder` |
| **Description** | Renames and/or moves a folder identified by `folderid` or `path` to either `topath` or `tofolderid`/`toname`. If `topath` is an existing folder to place the source folder without renaming, it MUST end with `/`. |

**Output:** Returns metadata of the renamed folder.

**Errors:** `1000`, `1002`, `1017`, `1037`, `2000`, `2001`, `2003`, `2004`, `2005`, `2008`, `2023`, `2042`, `2043`, `4000`, `5000`

---

### deletefolder

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/deletefolder` |
| **Description** | Deletes a folder. **Note:** Folders must be empty before calling this method. |

**Required (use `path` OR `folderid`):**

| Parameter | Description |
|---|---|
| `path` | string — path to the folder (discouraged) |
| `folderid` | int — ID of the folder |

**Output:** Returns metadata of the deleted folder.

**Errors:** `1000`, `1002`, `2000`, `2003`, `2005`, `2006`, `2007`, `2028`, `4000`, `5000`

---

### deletefolderrecursive

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/deletefolderrecursive` |
| **Description** | Deletes a folder recursively. **Warning:** This deletes files, directories, and removes sharing. Use with extreme care. |

**Required (use `path` OR `folderid`):**

| Parameter | Description |
|---|---|
| `path` | string — path to the folder (discouraged) |
| `folderid` | int — ID of the folder |

**Output:** Returns `deletedfiles` (int) and `deletedfolders` (int).

**Errors:** `1000`, `1002`, `2000`, `2003`, `2005`, `2006`, `2007`, `2028`, `4000`, `5000`

---

### copyfolder

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/copyfolder` |
| **Description** | Copies a folder identified by `folderid` or `path` to either `topath` or `tofolderid`. |

**Required:**

| Parameter | Description |
|---|---|
| `folderid` | int — source folder ID |
| `path` | string — source folder path |
| `tofolderid` | int — destination folder ID |
| `topath` | string — destination path |

**Optional:**

| Parameter | Description |
|---|---|
| `noover` | int — if set, no overwriting; returns error 2004 on conflict |
| `skipexisting` | int — if set, skip files that already exist |
| `copycontentonly` | int — if set, only copy contents of the source folder |

**Output:** Returns metadata of the created folder.

**Errors:** `1000`, `1002`, `1016`, `1037`, `2000`, `2001`, `2003`, `2004`, `2005`, `2008`, `2023`, `2119`, `2206`, `2207`, `2208`, `4000`, `5000`

---

## File

### uploadfile

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/uploadfile` |
| **Description** | Uploads one or more files. Uses POST with `multipart/form-data` encoding. Parameters must come before files. If a file with the same name exists, it is overwritten and the old one is saved as a revision. |

**Required:**

| Parameter | Description |
|---|---|
| `path` | string — path to the target folder (discouraged) |
| `folderid` | int — target folder ID |
| `filename` | string — the filename of each uploaded file |

**Optional:**

| Parameter | Description |
|---|---|
| `nopartial` | int — if set, partially uploaded files will not be saved |
| `progresshash` | string — hash used for observing upload progress |
| `renameifexists` | int — if set, uploaded file will be renamed on conflict |
| `mtime` | int — file modified time (unix timestamp) |
| `ctime` | int — file created time (requires `mtime`; unix timestamp) |

**Output:** Returns `fileids` array and `metadata` array.

**Errors:** `1000`, `2000`, `2001`, `2003`, `2005`, `2008`, `2041`, `4000`, `5000`, `5001`

---

### uploadprogress

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/uploadprogress` |
| **Description** | Gets upload progress. MUST be sent to the same API server handling the upload. |

**Required:**

| Parameter | Description |
|---|---|
| `progresshash` | string — same hash sent to `uploadfile` |

**Output:**

| Parameter | Description |
|---|---|
| `total` | int — total bytes to be transferred |
| `uploaded` | int — bytes uploaded so far |
| `currentfile` | string — filename currently being uploaded |
| `files` | array — metadata of already uploaded files |
| `finished` | bool — whether upload is finished |

**Errors:** `1000`, `1900`, `2000`, `4000`

---

### downloadfile

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/downloadfile` |
| **Description** | Downloads one or more files from URLs to a folder. The method returns when all files are downloaded. Use `progresshash` with `uploadprogress` to monitor. |

**Required:**

| Parameter | Description |
|---|---|
| `url` | string — links separated by whitespace |

**Optional:**

| Parameter | Description |
|---|---|
| `path` | string — destination folder path |
| `folderid` | string — destination folder ID |
| `target` | string — comma-separated URL-encoded desired filenames |

**Output:** Returns `metadata` array of all downloaded files.

**Errors:** `1000`, `1040`, `2000`, `2003`, `2005`, `2008`, `4000`, `5000`, `5001`

---

### downloadfileasync

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/downloadfileasync` |
| **Description** | Same as `downloadfile` but returns immediately when files are queued for download, not when they finish. Use `progresshash` with `uploadprogress` to monitor. |

**Required:**

| Parameter | Description |
|---|---|
| `url` | string — links separated by whitespace |

**Optional:**

| Parameter | Description |
|---|---|
| `path` | string — destination folder path |
| `folderid` | string — destination folder ID |
| `target` | string — comma-separated URL-encoded desired filenames |

**Errors:** `1000`, `1040`, `2000`, `2003`, `2005`, `2008`, `4000`, `5000`, `5001`

---

### copyfile

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/copyfile` |
| **Description** | Copies a file as another file in the user's filesystem. The target file will be a separate, newly created, independent file. Useful for creating public links from shared files. |

**Required (use `fileid` or `path` for source; `tofolderid`+`toname` or `topath` for destination):**

| Parameter | Description |
|---|---|
| `fileid` | int — source file ID |
| `path` | string — source file path |
| `tofolderid` | int — destination folder ID |
| `topath` | string — destination path |

**Optional:**

| Parameter | Description |
|---|---|
| `toname` | string — destination filename (defaults to original) |
| `noover` | int — if set, no overwriting on conflict |
| `mtime` | int — file modified time (unix timestamp) |
| `ctime` | int — file created time (requires `mtime`; unix timestamp) |

**Output:** Returns metadata of the copy.

**Errors:** `1000`, `1004`, `1016`, `2000`, `2001`, `2002`, `2003`, `2004`, `2008`, `2009`, `2010`, `4000`, `5000`

---

### checksumfile

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/checksumfile` |
| **Description** | Calculates checksums of a file. SHA1 is returned from both US and Europe servers. MD5 is US-only. SHA256 is Europe-only. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Output:** Returns `sha1`, `md5` (US only), `sha256` (EU only), and `metadata`.

**Errors:** `1000`, `1004`, `2000`, `2002`, `2003`, `2009`, `2010`, `4000`, `5000`

---

### deletefile

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/deletefile` |
| **Description** | Deletes a file identified by `fileid` or `path`. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Output:** Returns file metadata with `isdeleted` set.

**Errors:** `1000`, `1004`, `2000`, `2002`, `2003`, `2009`, `2010`, `4000`, `5000`

---

### renamefile

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/renamefile` |
| **Description** | Renames and/or moves a file. If the destination file already exists, it is replaced atomically, and `deletedfileid` is included in the response metadata. |

**Required (use `fileid` or `path` for source; provide at least one of `topath`, `tofolderid`, `toname`):**

| Parameter | Description |
|---|---|
| `fileid` | int — source file ID |
| `path` | string — source file path |
| `topath` | string — destination path (must end with `/` if only specifying folder) |
| `tofolderid` | int — destination folder ID |
| `toname` | string — destination filename |

**Output:** Returns renamed file's metadata.

**Errors:** `1000`, `1004`, `1037`, `2000`, `2001`, `2002`, `2003`, `2005`, `2008`, `2009`, `2010`, `4000`, `5000`

---

### stat

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/stat` |
| **Description** | Returns information about a file pointed to by `fileid` or `path`. Using `fileid` is recommended. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path (discouraged) |

**Output:** Returns `metadata`.

**Errors:** `1000`, `2000`, `2001`, `2003`, `2041`, `4000`, `5000`, `5001`

---

## Auth

### sendverificationemail

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/sendverificationemail` |
| **Description** | Sends an email to the logged-in user with an activation link. Takes no parameters. |

**Errors:** `1000`, `2000`, `2013`, `4000`

---

### verifyemail

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/verifyemail` |
| **Description** | Verifies an email with the activation code from the validation email. Note: the code might be for a different user than the currently logged-in one. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — activation code from email |

**Output:** Returns `email` (string) and `userid` (int).

**Errors:** `1000`, `1022`, `2000`, `2012`, `2013`, `4000`, `5000`

---

### changepassword

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/changepassword` |
| **Description** | Changes the current user's password. New password must be ≥6 chars, ≥4 different characters, cannot be all consecutive characters, and cannot start/end with whitespace. |

**Required:**

| Parameter | Description |
|---|---|
| `oldpassword` | string — current password |
| `newpassword` | string — desired new password |

**Errors:** `1000`, `1031`, `1032`, `2000`, `2030`, `2031`, `2032`, `2033`, `2034`, `2035`, `4000`, `5000`

---

### lostpassword

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/lostpassword` |
| **Description** | Sends password reset instructions to the given email. A successful reply is sent even if no user exists with that email (for security). |

**Required:**

| Parameter | Description |
|---|---|
| `mail` | string — user's email |

**Errors:** `1000`, `1033`, `2000`, `4000`

---

### resetpassword

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/resetpassword` |
| **Description** | Resets a user's password using the code from `lostpassword`. Subject to the same password checks as `changepassword`. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — code from email |
| `newpassword` | string — new password |

**Errors:** `1000`, `1022`, `1032`, `2000`, `2012`, `2032`, `2033`, `2034`, `2035`, `2036`, `4000`, `5000`

---

### register

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/register` |
| **Description** | Registers a new user. Parameter `termsaccepted` MUST be set to `yes`. Password is subject to the same checks as `changepassword`. |

**Required:**

| Parameter | Description |
|---|---|
| `mail` | string — user's email |
| `password` | string — chosen password |

**Optional:**

| Parameter | Description |
|---|---|
| `language` | string — one of the supported languages |
| `referer` | string — userid of the referring user |

**Errors:** `1000`, `1033`, `1034`, `2000`, `2018`, `2032`, `2033`, `2034`, `2035`, `2037`, `2038`, `4000`, `5000`

---

### invite

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/invite` |
| **Description** | Returns a URL to a registration page with a referrer code that credits free space upon registration. |

**Output:**

| Field | Description |
|---|---|
| `url` | string — registration page address |
| `spacelimitreached` | bool — whether maximum free space is reached |

**Errors:** `1000`, `2000`, `4000`, `5000`

---

### userinvites

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/userinvites` |
| **Description** | Returns a list of the current user's invitations. |

**Output:** Returns `invites` array with objects containing:

| Field | Description |
|---|---|
| `email` | string — email of the invited user (partially hidden) |
| `is_pending` | bool — whether the invitation is pending |

**Errors:** `1000`, `2000`, `4000`, `5000`

---

### logout

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/logout` |
| **Description** | Invalidates the current authentication token. |

**Output:** Returns `auth_deleted` (bool).

**Errors:** `1000`, `2000`, `4000`

---

### listtokens

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/listtokens` |
| **Description** | Returns currently active tokens associated with the current user. |

**Output:** Returns `tokens` array with objects containing:

| Field | Description |
|---|---|
| `tokenid` | int — token identification number |
| `device` | string — device information |
| `created` | datetime — when the token was created |
| `expires_inactive` | datetime — expiry if unused |
| `expires` | datetime — absolute expiry |

**Errors:** `1000`, `2000`, `4000`

---

### deletetoken

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/deletetoken` |
| **Description** | Invalidates an authentication token identified by `tokenid` (from `listtokens`). |

**Errors:** `1000`, `1076`, `2000`, `2102`, `4000`

---

### sendchangemail

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/sendchangemail` |
| **Description** | Sends an email to the logged-in user with a link for changing their email. If `newmail` and `code` are provided, sends a confirmation email to the new address. |

**Optional:**

| Parameter | Description |
|---|---|
| `newmail` | string — new email address |
| `code` | string — code from email |

**Errors:** `1000`, `2000`, `2012`, `2038`, `2074`, `2271`

---

### changemail

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/changemail` |
| **Description** | Changes the current user's email using a code from `sendchangemail`. |

**Required:**

| Parameter | Description |
|---|---|
| `password` | string — current password |
| `code` | string — code from email |

**Errors:** `1000`, `1022`, `1034`, `2000`, `2012`, `2038`, `2074`, `2271`, `2272`

---

### senddeactivatemail

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/senddeactivatemail` |
| **Description** | Sends an email to the logged-in user with a deactivation link. |

**Errors:** `1000`, `2000`

---

### deactivateuser

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/deactivateuser` |
| **Description** | Deactivates the current user. |

**Required:**

| Parameter | Description |
|---|---|
| `password` | string — current password |
| `code` | string — code from email |

**Errors:** `1000`, `1022`, `1034`, `2000`, `2012`, `2074`, `2272`

---

## Streaming

> **Note:** Streaming methods cannot be used from web applications. Referrer is restricted to pcloud.com.

### getfilelink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getfilelink` |
| **Description** | Returns a download link for a file. You must construct the URL by concatenating `https://` + one of the `hosts` + the `path`. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Optional:**

| Parameter | Description |
|---|---|
| `forcedownload` | int — serve with `application/octet-stream` content type |
| `contenttype` | string — custom Content-Type |
| `maxspeed` | int — download speed limit in bytes/sec |
| `skipfilename` | int — exclude filename from generated link |

**Output:** Returns `hosts` (array), `path` (string), `expires` (datetime).

**Errors:** `1000`, `1004`, `1005`, `2000`, `2002`, `2003`, `2009`, `2010`, `2011`, `4000`, `5002`

---

### getvideolink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getvideolink` |
| **Description** | Returns a streaming link for a video file with transcoding options. Output is FLV container with x264 video and mp3 audio. Supports adaptive bitrate by default. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Optional:**

| Parameter | Description |
|---|---|
| `abitrate` | int — audio bitrate in kbps (16–320) |
| `vbitrate` | int — video bitrate in kbps (16–4000) |
| `resolution` | string — WIDTHxHEIGHT (64x64 to 1280x960) |
| `fixedbitrate` | bool — disable adaptive streaming |
| `forcedownload` | int — force download content type |
| `contenttype` | string — custom Content-Type |
| `maxspeed` | int — download speed limit |
| `skipfilename` | int — exclude filename from link |

**Output:** Returns `hosts`, `path`, `expires`.

**Errors:** `1000`, `1004`, `1005`, `2000`, `2002`, `2003`, `2009`, `2010`, `2044`, `4000`, `5002`

---

### getvideolinks

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getvideolinks` |
| **Description** | Returns a `variants` array of different quality/resolution versions of a video. Each variant includes `path`, `hosts`, `width`, `height`, `duration`, `fps`, `videobitrate`, `audiobitrate`, `videocodec`, `audiocodec`. The original has `isoriginal: true`. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Optional:**

| Parameter | Description |
|---|---|
| `forcedownload` | int — force download content type |
| `contenttype` | string — custom Content-Type |
| `maxspeed` | int — download speed limit |
| `skipfilename` | bool — exclude filename from link |

**Errors:** `1000`, `1004`, `1005`, `2000`, `2002`, `2003`, `2009`, `2010`, `2044`, `4000`, `5002`

---

### getaudiolink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getaudiolink` |
| **Description** | Returns a streaming link for an audio file in mp3 format. Default bitrate is 192kbps. Can extract audio from video files. Supports the `start` GET parameter on the returned link. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Optional:**

| Parameter | Description |
|---|---|
| `forcedownload` | int — force download content type |
| `contenttype` | string — custom Content-Type |
| `abitrate` | int — audio bitrate in kbps (16–320) |

**Output:** Returns `hosts`, `path`, `expires`.

**Errors:** `1000`, `1004`, `1005`, `2000`, `2002`, `2003`, `2009`, `2010`, `2044`, `4000`, `5002`

---

### gethlslink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/gethlslink` |
| **Description** | Returns links to an m3u8 playlist for HTTP Live Streaming of a video file. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Optional:**

| Parameter | Description |
|---|---|
| `abitrate` | int — audio bitrate in kbps (16–320) |
| `vbitrate` | int — video bitrate in kbps (16–4000) |
| `resolution` | string — WIDTHxHEIGHT |
| `skipfilename` | int — exclude filename from link |

**Output:** Returns `hosts`, `path`, `expires`.

**Errors:** `1000`, `1004`, `2000`, `2002`, `2003`, `2009`, `2010`, `2044`, `4000`, `5002`

---

### gettextfile

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/gettextfile` |
| **Description** | Downloads a file in a different character encoding. The file is streamed directly by the API server (no content server links). |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Optional:**

| Parameter | Description |
|---|---|
| `fromencoding` | string — original encoding (default: guessed) |
| `toencoding` | string — output encoding (default: utf-8) |
| `forcedownload` | int — force download content type |
| `contenttype` | string — custom Content-Type |

**Errors:** `1000`, `1004`, `1005`, `2000`, `2002`, `2003`, `2009`, `2010`, `2061`, `4000`, `5002`

---

## Archiving

### getzip

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getzip` |
| **Description** | Streams a zip file of the requested tree over the current API connection. The archive is constructed on-the-fly, so downloads start instantly. Uses zip64 format for files > 4GB or > 65535 entries. |

**Optional:**

| Parameter | Description |
|---|---|
| `forcedownload` | int — if set, content-type is `application/octet-stream` |
| `filename` | string — Content-Disposition filename (must include `.zip`) |
| `timeoffset` | string — timezone offset (e.g., `+0300`, `-05:00`) |

**Errors:** `1000`, `1017`, `1018`, `2000`, `2009`, `4000`

---

### getziplink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getziplink` |
| **Description** | Returns a download link for a zip archive. Less efficient than `getzip` as the archive is created server-side first. Returns `hosts`, `path`, and `expires` like `getfilelink`. |

**Optional:**

| Parameter | Description |
|---|---|
| `maxspeed` | int — download speed limit (bytes/sec) |
| `forcedownload` | int — force `application/octet-stream` content type |
| `filename` | string — Content-Disposition filename (must include `.zip`) |
| `timeoffset` | string — timezone offset |

**Errors:** `1000`, `1017`, `1018`, `2000`, `2009`, `2011`, `4000`, `5001`, `5002`

---

### savezip

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/savezip` |
| **Description** | Creates a zip file in the user's filesystem. Use `progresshash` with `savezipprogress` to monitor. |

**Optional:**

| Parameter | Description |
|---|---|
| `timeoffset` | string — timezone offset |
| `topath` | string — destination path |
| `tofolderid` | int — destination folder ID |
| `toname` | string — filename for the zip |
| `progresshash` | string — key to retrieve progress |

**Output:** Returns metadata of the created zip file.

**Errors:** `1000`, `1016`, `1017`, `1018`, `2000`, `2001`, `2002`, `2003`, `2004`, `2008`, `2009`, `4000`, `5000`, `5001`

---

### extractarchive

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/extractarchive` |
| **Description** | Extracts an archive file from the user's filesystem. Runs extraction for about 2 seconds; if it doesn't finish, returns `progresshash` for use with `extractarchiveprogress`. |

**Optional:**

| Parameter | Description |
|---|---|
| `nooutput` | bool — if set, extraction output is not returned |
| `overwrite` | string — `rename` (default), `overwrite`, or `skip` |
| `password` | string — password for protected archives |

**Output:** Returns `finished` (bool), `progresshash` (if not finished), `output` array, `lines` count.

**Errors:** `1000`, `1004`, `1037`, `2000`, `2002`, `2003`, `2005`, `2009`, `2010`, `2059`, `3006`, `4000`, `7009`

---

### extractarchiveprogress

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/extractarchiveprogress` |
| **Description** | Returns output and completion status of an extraction started by `extractarchive`. |

**Optional:**

| Parameter | Description |
|---|---|
| `lines` | int — number of output lines to skip |

**Output:** Returns `finished` (bool), `output` array, `lines` count.

**Errors:** `1000`, `1052`, `1900`, `2000`, `4000`

---

### savezipprogress

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/savezipprogress` |
| **Description** | Returns progress of a zip creation started by `savezip`. The process is ready when `files` equals `totalfiles`. |

**Optional:**

| Parameter | Description |
|---|---|
| `progresshash` | string — the key from `savezip` |

**Output:**

| Field | Description |
|---|---|
| `files` | int — count of zipped files |
| `totalfiles` | int — total files to zip |
| `bytes` | int — size of zipped files |
| `totalbytes` | int — total size to zip |

**Errors:** `1000`, `1901`, `2000`, `4000`, `5000`

---

## Sharing

### sharefolder

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/sharefolder` |
| **Description** | Shares a folder with another user. Permissions: 0 = read-only, 1 = create, 2 = modify, 4 = delete (combine with sum/OR). |

**Required (use `path` OR `folderid`):**

| Parameter | Description |
|---|---|
| `folderid` | int — folder ID |
| `path` | string — folder path |
| `mail` | string — email of the target user |
| `permissions` | int — bitwise combination of permission flags |

**Optional:**

| Parameter | Description |
|---|---|
| `name` | string — share name (defaults to folder name) |
| `message` | string — message to the receiving user |

**Errors:** `1000`, `1002`, `1023`, `1024`, `2000`, `2001`, `2005`, `2014`, `2015`, `2016`, `2017`, `2018`, `2019`, `2020`, `2024`, `4000`, `5000`

---

### listshares

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/listshares` |
| **Description** | Lists current shares and share requests. |

**Optional:**

| Parameter | Description |
|---|---|
| `norequests` | int — hide share requests |
| `noshares` | int — hide established shares |
| `noincoming` | int — hide incoming sub-objects |
| `nooutgoing` | int — hide outgoing sub-objects |

**Output:** Returns `shares` and `requests` objects, each with `incoming` and `outgoing` sub-objects.

**Errors:** `1000`, `2000`, `4000`

---

### sharerequestinfo

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/sharerequestinfo` |
| **Description** | Returns information about a share request from the code sent to the user's email. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — code from email |

**Errors:** `1000`, `1022`, `2000`, `2021`, `4000`

---

### cancelsharerequest

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/cancelsharerequest` |
| **Description** | Cancels a share request sent by the current user. |

**Required:**

| Parameter | Description |
|---|---|
| `sharerequestid` | int — request ID |

**Errors:** `1000`, `1026`, `2000`, `2021`, `4000`

---

### acceptshare

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/acceptshare` |
| **Description** | Accepts a share request. Can optionally specify a mount point and auto-accept future requests from the sharing user. |

**Required (use `sharerequestid` OR `code`):**

| Parameter | Description |
|---|---|
| `sharerequestid` | int — request ID |
| `code` | string — code from email |

**Optional:**

| Parameter | Description |
|---|---|
| `name` | string — folder name (defaults to share name) |
| `folderid` | int — mount folder ID |
| `path` | string — mount path |
| `always` | int — auto-accept future requests from this user |

**Errors:** `1000`, `1025`, `2000`, `2001`, `2002`, `2020`, `2021`, `2022`, `2023`, `2024`, `4000`, `5000`

---

### declineshare

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/declineshare` |
| **Description** | Declines a share request. |

**Required (use `sharerequestid` OR `code`):**

| Parameter | Description |
|---|---|
| `sharerequestid` | int — request ID |
| `code` | string — code from email |

**Optional:**

| Parameter | Description |
|---|---|
| `block` | int — auto-decline all future requests from this user |

**Errors:** `1000`, `1025`, `2000`, `2021`, `2022`, `4000`

---

### removeshare

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/removeshare` |
| **Description** | Removes an active share (incoming or outgoing). |

**Required:**

| Parameter | Description |
|---|---|
| `shareid` | int — share ID from `listshares` |

**Errors:** `1000`, `1027`, `2000`, `2025`, `4000`, `5000`

---

### changeshare

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/changeshare` |
| **Description** | Changes permissions of an outgoing share. Only the folder owner may use this. |

**Required:**

| Parameter | Description |
|---|---|
| `shareid` | int — share ID from `listshares` |
| `permissions` | string — new permissions |

**Errors:** `1000`, `1024`, `1027`, `2000`, `2025`, `4000`, `5000`

---

## Public Links

### getfilepublink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getfilepublink` |
| **Description** | Creates and returns a public link to a file. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Optional:**

| Parameter | Description |
|---|---|
| `expire` | datetime — link expiration |
| `maxdownloads` | int — max downloads |
| `maxtraffic` | int — max traffic in bytes |
| `shortlink` | int — also generate a short link |
| `linkpassword` | string — password for the link |

**Output:** Returns `linkid`, `code`, `link`. If `shortlink` was set: also `shortcode` and `shortlink`.

**Errors:** `1000`, `1004`, `1013`, `2000`, `2002`, `2009`, `2010`, `2014`, `2026`, `4000`, `5000`

---

### getfolderpublink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getfolderpublink` |
| **Description** | Creates and returns a public link to a folder. `maxdownloads` limits total downloads from this folder. |

**Required (use `folderid` OR `path`):**

| Parameter | Description |
|---|---|
| `folderid` | int — folder ID |
| `path` | string — folder path |

**Optional:**

| Parameter | Description |
|---|---|
| `expire` | datetime — link expiration |
| `maxdownloads` | int — max total downloads |
| `maxtraffic` | int — max traffic in bytes |
| `shortlink` | int — also generate a short link |
| `linkpassword` | string — password for the link |

**Output:** Returns `linkid`, `code`, `link`. If `shortlink` was set: also `shortcode` and `shortlink`.

**Errors:** `1000`, `1002`, `1013`, `2000`, `2005`, `2014`, `2015`, `2026`, `4000`, `5000`

---

### gettreepublink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/gettreepublink` |
| **Description** | Creates a public link to a virtual folder defined by a tree. **Note:** Tree links are snapshots and will not follow future updates. |

Tree parameters: `fileids` (comma-separated), `folderids` (comma-separated), or `folderid:` (contents dumped into virtual folder). Requires `name` parameter.

**Optional:** Same as `getfilepublink` (`expire`, `maxdownloads`, `maxtraffic`, `shortlink`, `linkpassword`).

**Output:** Same as `getfilepublink`.

**Errors:** `1000`, `1013`, `1017`, `1018`, `1039`, `2000`, `2009`, `2014`, `4000`, `5000`

---

### showpublink

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/showpublink` |
| **Description** | Returns metadata of the object a public link points to. For folders, `contents` will be present recursively. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |

**Errors:** `1000`, `1028`, `2000`, `4000`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getpublinkdownload

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpublinkdownload` |
| **Description** | Returns download link(s) for a public link's file. Only call this when the user intends to actually download. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |
| `fileid` | int — required if the link points to a folder |

**Optional:**

| Parameter | Description |
|---|---|
| `forcedownload` | int — force `application/octet-stream` |
| `contenttype` | string — custom Content-Type |
| `maxspeed` | int — download speed limit |
| `skipfilename` | int — exclude filename from link |

**Output:** Returns `hosts`, `path`, `expires`.

**Errors:** `1000`, `1004`, `1005`, `1028`, `1029`, `2000`, `2002`, `2009`, `2010`, `2011`, `4000`, `5002`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### copypubfile

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/copypubfile` |
| **Description** | Copies a file from a public link to the current user's filesystem. No actual download/traffic occurs, so this works even when the link is out of downloads/traffic. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |
| `fileid` | int — required if the link points to a folder |
| `tofolderid` | int — destination folder ID |
| `topath` | string — destination path |

**Optional:**

| Parameter | Description |
|---|---|
| `toname` | string — destination filename |
| `noover` | int — no overwrite on conflict |

**Output:** Returns metadata of the copied file.

**Errors:** `1000`, `1004`, `1016`, `1028`, `1029`, `2000`, `2001`, `2002`, `2003`, `2004`, `2008`, `2009`, `2010`, `4000`, `5000`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### listpublinks

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/listpublinks` |
| **Description** | Returns a list of the current user's public links in `publinks` array. Each link includes `linkid`, `code`, `link`, `created`, `modified`, `metadata`, `downloads`, `traffic`, and optionally `shortcode`, `shortlink`, `expires`, `maxdownloads`, `maxtraffic`. |

**Errors:** `1000`, `2000`, `4000`, `5000`

---

### listplshort

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/listplshort` |
| **Description** | Returns a short/summary list of the current user's public links. |

**Errors:** `1000`, `2000`, `4000`

---

### deletepublink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/deletepublink` |
| **Description** | Deletes a public link. |

**Required:**

| Parameter | Description |
|---|---|
| `linkid` | int — link ID |

**Errors:** `1000`, `1030`, `2000`, `2027`, `4000`, `5000`

---

### changepublink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/changepublink` |
| **Description** | Modifies a public link. |

**Required:**

| Parameter | Description |
|---|---|
| `linkid` | int — link ID |

**Optional (at least one must be specified):**

| Parameter | Description |
|---|---|
| `shortlink` | int — create a short link |
| `deleteshortlink` | int — delete the short link |
| `expire` | datetime — new expiration date |
| `deleteexpire` | datetime — remove expiration |
| `maxtraffic` | int — traffic limit (0 = unlimited) |
| `maxdownloads` | int — downloads limit (0 = unlimited) |
| `linkpassword` | string — password for the link |

**Errors:** `1000`, `1013`, `1030`, `2000`, `2027`, `4000`, `5000`

---

### getpubthumb

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpubthumb` |
| **Description** | Returns a thumbnail of a public file over the current API connection. Same as `getthumb`, but works on a public file identified by `code` (and `fileid` if the link is to a folder). |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |
| `fileid` | int — file ID (required if the link is to a folder) |
| `size` | string — WIDTHxHEIGHT |

**Optional:**

| Parameter | Description |
|---|---|
| `crop` | int — if set, the thumb will be cropped to exact size |
| `type` | string — `png` for PNG format (default is JPEG) |

**Errors:** `1000`, `1004`, `1014`, `1015`, `1028`, `1029`, `2000`, `2002`, `2009`, `2010`, `3001`, `4000`, `5002`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getpubthumblink

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpubthumblink` |
| **Description** | Returns a link to a thumbnail of a public file. Same as `getthumblink`, but works on a public file identified by `code` (and `fileid` if the link is to a folder). |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |
| `fileid` | int — file ID (required if the link is to a folder) |
| `size` | string — WIDTHxHEIGHT |

**Optional:**

| Parameter | Description |
|---|---|
| `crop` | int — if set, the thumb will be cropped to exact size |
| `type` | string — `png` for PNG format (default is JPEG) |

**Errors:** `1000`, `1004`, `1014`, `1015`, `1028`, `1029`, `2000`, `2002`, `2009`, `2010`, `3001`, `4000`, `5002`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getpubthumbslinks

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpubthumbslinks` |
| **Description** | Returns links to thumbnails for multiple files from a public link. Same as `getthumbslinks`, but works on a public file identified by `code` (and `fileid` if the link is to a folder). |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |
| `fileid` | int — file ID (required if the link is to a folder) |
| `size` | string — WIDTHxHEIGHT |

**Optional:**

| Parameter | Description |
|---|---|
| `crop` | int — if set, the thumb will be cropped to exact size |
| `type` | string — `png` for PNG format (default is JPEG) |

**Errors:** `1000`, `1015`, `1028`, `1038`, `2000`, `4000`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### savepubthumb

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/savepubthumb` |
| **Description** | Creates a thumbnail of a public link file and saves it in the current user's filesystem. Same as `savethumb`, but works on a public file identified by `code` (and `fileid` if the link is to a folder). |

**Required (use `topath` OR `tofolderid`+`toname`):**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |
| `fileid` | int — file ID (required if the link is to a folder) |
| `size` | string — WIDTHxHEIGHT |
| `topath` | string — destination file path |
| `tofolderid` | int — destination folder ID |
| `toname` | string — destination filename |

**Optional:**

| Parameter | Description |
|---|---|
| `crop` | int — if set, the thumb will be cropped to exact size |
| `type` | string — `png` for PNG format (default is JPEG) |
| `noover` | int — if set, error on overwrite |

**Errors:** `1000`, `1014`, `1015`, `1016`, `1029`, `2000`, `2001`, `2002`, `2003`, `2004`, `2008`, `2009`, `3001`, `4000`, `5000`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getpubzip

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpubzip` |
| **Description** | Creates a zip archive of a public link's files and streams it as the response. Same as `getzip`, but works on a public file identified by `code`. The `filename`, `forcedownload`, and `timeoffset` optional parameters work the same way as in `getzip`. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |

**Optional:**

| Parameter | Description |
|---|---|
| `forcedownload` | int — if set, Content-Type is `application/octet-stream`; otherwise `application/zip` |
| `filename` | string — sent back as `Content-Disposition` header (MUST include `.zip` extension) |
| `timeoffset` | string — desired time offset |

**Output:** Streams a zip archive over the current API connection with all files/directories in the requested tree.

**Errors:** `1000`, `1017`, `1018`, `1028`, `2000`, `4000`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getpubziplink

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpubziplink` |
| **Description** | Creates a link to a zip archive of a public link's files. Same as `getziplink`, but works on a public file identified by `code`. **Note:** `getpubziplink` is slower and less efficient than `getpubzip` — it takes time to generate the zip file, whereas `getpubzip` starts the download right away. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |

**Optional:**

| Parameter | Description |
|---|---|
| `forcedownload` | int — if set, Content-Type is `application/octet-stream`; otherwise `application/zip` |
| `filename` | string — sent back as `Content-Disposition` header (MUST include `.zip` extension) |
| `timeoffset` | string — desired time offset |

**Errors:** `1000`, `1017`, `1018`, `1028`, `2000`, `2011`, `4000`, `5001`, `5002`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### savepubzip

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/savepubzip` |
| **Description** | Creates a zip archive of a public link's files and saves it to the current user's filesystem. Same as `savezip`, but works on a public file identified by `code`. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |

**Optional:**

| Parameter | Description |
|---|---|
| `timeoffset` | string — desired time offset |
| `topath` | string — path where to save the zip archive |
| `tofolderid` | int — folder ID of the folder where to save the zip archive |
| `toname` | string — filename of the desired zip archive |

**Output:** If successful, creates the zip archive and returns its metadata.

**Errors:** `1000`, `1016`, `1017`, `1018`, `1028`, `2000`, `2001`, `2002`, `2003`, `2004`, `2008`, `4000`, `5000`, `5001`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getpubvideolinks

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpubvideolinks` |
| **Description** | Returns a `variants` array of different quality/resolution versions of a video in a public link. Same as `getvideolinks`, but works on a public file identified by `code` (and `fileid` if the link is to a folder). **Note:** This method can't be used from web applications — referrer is restricted to pcloud.com. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |

**Optional:**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID (required if the link is to a folder) |
| `forcedownload` | int — force `application/octet-stream` Content-Type |
| `contenttype` | string — custom Content-Type |
| `maxspeed` | int — limit the download speed |
| `skipfilename` | bool — exclude filename from the generated link |

**Errors:** `1000`, `1005`, `1028`, `1029`, `2000`, `2009`, `2044`, `4000`, `5002`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getpubaudiolink

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpubaudiolink` |
| **Description** | Creates a link to an audio file from a public link, suitable for streaming. Same as `getaudiolink`, but works on a public file identified by `code` (and `fileid` if the link is to a folder). **Note:** This method can't be used from web applications — referrer is restricted to pcloud.com. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |

**Optional:**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID (required if the link is to a folder) |
| `forcedownload` | int — force `application/octet-stream` Content-Type |
| `contenttype` | string — custom Content-Type |
| `abitrate` | int — audio bit rate in kilobits (16–320) |

**Errors:** `1000`, `1004`, `1005`, `1028`, `1029`, `2000`, `2002`, `2009`, `2010`, `2044`, `4000`, `5002`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getpubtextfile

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/getpubtextfile` |
| **Description** | Downloads a text file from a public link with optional character encoding conversion. The file is streamed as the response. Same as `gettextfile`, but works on a public file identified by `code` (and `fileid` if the link is to a folder). |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — `code` or `shortcode` |

**Optional:**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID (required if the link is to a folder) |
| `fromencoding` | string — original character encoding of the file (default: guess) |
| `toencoding` | string — requested character encoding of the output (default: utf-8) |
| `forcedownload` | int — force `application/octet-stream` Content-Type |
| `contenttype` | string — custom Content-Type |

**Errors:** `1000`, `1005`, `1028`, `1029`, `2000`, `2002`, `2009`, `2010`, `2061`, `4000`, `5002`, `7001`, `7002`, `7004`, `7005`, `7006`

---

### getcollectionpublink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getcollectionpublink` |
| **Description** | Generates a public link to a collection owned by the current user. Has the same optional parameters as `getfilepublink`. **Note:** Public links pointing to a collection are real-time images of the collection, while tree links are snapshots. |

**Required:**

| Parameter | Description |
|---|---|
| `collectionid` | int — the ID of the collection |

**Optional:**

| Parameter | Description |
|---|---|
| `expire` | datetime — when the link will stop working |
| `maxdownloads` | int — maximum number of downloads |
| `maxtraffic` | int — maximum traffic in bytes |
| `shortlink` | int — also generate a short link |

**Output:** Returns `linkid`, `code`, `link`. If `shortlink` was set: also `shortcode` and `shortlink`.

**Errors:** `1000`, `1013`, `1057`, `2000`, `2014`, `2065`, `4000`, `5000`

---

## Thumbnails

### getthumblink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getthumblink` |
| **Description** | Returns a link to a thumbnail. Only works for files with `thumb: true` in metadata. Width must be 16–2048 (divisible by 4 or 5), height must be 16–1024 (divisible by 4 or 5). Use `crop` for exact dimensions. Clients should cache thumbs and monitor the file's `hash` for changes. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |
| `size` | string — WIDTHxHEIGHT |

**Optional:**

| Parameter | Description |
|---|---|
| `crop` | int — crop to exact size |
| `type` | string — `png` for PNG format (default is JPEG) |

**Output:** Returns `hosts`, `path`, `expires`, `size`.

**Errors:** `1000`, `1004`, `1014`, `1015`, `2000`, `2002`, `2003`, `2009`, `2010`, `3001`, `4000`, `5002`

---

### getthumbslinks

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getthumbslinks` |
| **Description** | Returns thumbnail links for multiple files at once. Preferred over multiple `getthumblink` calls — connects to multiple storage servers simultaneously. |

**Required:**

| Parameter | Description |
|---|---|
| `fileids` | string — comma-separated file IDs |
| `size` | string — WIDTHxHEIGHT |

**Optional:**

| Parameter | Description |
|---|---|
| `crop` | int — crop to exact size |
| `type` | string — `png` for PNG format |

**Output:** Returns `thumbs` array with `result`, `fileid`, `path`, `hosts`, `expires`, `size` for each.

**Errors:** `1000`, `1015`, `1038`, `2000`, `4000`

---

### getthumb

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/getthumb` |
| **Description** | Returns a thumbnail over the current API connection (no content server link). Only makes sense when reusing an expensive SSL connection. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |
| `size` | string — WIDTHxHEIGHT |

**Optional:**

| Parameter | Description |
|---|---|
| `crop` | int — crop to exact size |
| `type` | string — `png` for PNG format |

**Errors:** `1000`, `1004`, `1014`, `1015`, `2000`, `2002`, `2003`, `2009`, `2010`, `3001`, `4000`, `5002`

---

### savethumb

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/savethumb` |
| **Description** | Creates a thumbnail and saves it to the user's filesystem. |

**Required (use `fileid` or `path`; use `topath` or `tofolderid`+`toname`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |
| `size` | string — WIDTHxHEIGHT |
| `topath` | string — destination path |
| `tofolderid` | int — destination folder ID |
| `toname` | string — destination filename |

**Optional:**

| Parameter | Description |
|---|---|
| `crop` | int — crop to exact size |
| `type` | string — `png` for PNG format |
| `noover` | int — error on overwrite |

**Output:** Returns `metadata`, `width`, `height`.

**Errors:** `1000`, `1004`, `1014`, `1015`, `1016`, `2000`, `2001`, `2002`, `2003`, `2004`, `2008`, `2009`, `2010`, `3001`, `4000`, `5000`

---

## Upload Links

### createuploadlink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/createuploadlink` |
| **Description** | Creates an upload link. The folder must be owned by the user. Comments are the only info uploaders see — they won't know the owner's username or folder name. |

**Required (use `path` OR `folderid`):**

| Parameter | Description |
|---|---|
| `folderid` | int — target folder ID |
| `path` | string — target folder path |
| `comment` | string — instructions for uploaders |

**Optional:**

| Parameter | Description |
|---|---|
| `expire` | datetime — expiration date |
| `maxspace` | int — max total size in bytes |
| `maxfiles` | int — max number of files |

**Output:** Returns `uploadlinkid`, `link`, `mail`, `code`.

**Errors:** `1000`, `1002`, `1013`, `1035`, `2000`, `2005`, `2014`, `2039`, `4000`, `5000`

---

### listuploadlinks

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/listuploadlinks` |
| **Description** | Lists all upload links in `uploadlinks` array. |

**Output per link:** `uploadlinkid`, `link`, `mail`, `code`, `comment`, `files`, `space`, `metadata`, `created`, `modified`. Optionally: `expire`, `maxspace`, `maxfiles`.

**Errors:** `1000`, `2000`, `4000`

---

### deleteuploadlink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/deleteuploadlink` |
| **Description** | Deletes an upload link. |

**Required:**

| Parameter | Description |
|---|---|
| `uploadlinkid` | int — upload link ID |

**Errors:** `1000`, `1036`, `2000`, `2040`, `4000`, `5000`

---

### changeuploadlink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/changeuploadlink` |
| **Description** | Modifies an upload link's expiration, space limit, or file limit. |

**Required:**

| Parameter | Description |
|---|---|
| `uploadlinkid` | int — upload link ID |

**Optional:**

| Parameter | Description |
|---|---|
| `expire` | datetime — set expiration date |
| `deleteexpire` | int — remove expiration |
| `maxspace` | int — max space in bytes (0 = unlimited) |
| `maxfiles` | int — max files (0 = unlimited) |

**Errors:** `1000`, `1013`, `1036`, `2000`, `2040`, `4000`, `5000`

---

### showuploadlink

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/showuploadlink` |
| **Description** | Returns the upload link's comment and mail. Returns proper 7xxx errors for deleted/expired links. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — upload link code |

**Errors:** `1000`, `1013`, `1036`, `2000`, `2040`, `4000`, `5000`

---

### uploadtolink

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/uploadtolink` |
| **Description** | Uploads files to an upload link. Similar to `uploadfile` but files are always renamed on conflict. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — upload link code |

**Optional:**

| Parameter | Description |
|---|---|
| `nopartial` | int — don't save partial uploads |
| `progresshash` | string — for monitoring with `uploadlinkprogress` |

**Errors:** `1000`, `2000`, `2001`, `2041`, `4000`, `5000`, `5001`, `7002`, `7004`, `7007`, `7008`

---

### uploadlinkprogress

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/uploadlinkprogress` |
| **Description** | Monitors upload progress for an upload link. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — upload link code |
| `progresshash` | string — hash from `uploadtolink` |

**Output:** Same as `uploadprogress` but without `files`.

**Errors:** `1000`, `1022`, `1900`, `2000`, `4000`

---

### copytolink

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/copytolink` |
| **Description** | Copies a file from the current user's filesystem to an upload link. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — upload link code |
| `fileid` | int — source file ID |
| `path` | string — source file path |

**Optional:**

| Parameter | Description |
|---|---|
| `toname` | string — name to save as (defaults to original) |

**Errors:** `1000`, `1004`, `2000`, `2001`, `2002`, `2003`, `2009`, `2010`, `4000`, `5000`, `7002`, `7004`, `7007`, `7008`

---

## Revisions

### listrevisions

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/listrevisions` |
| **Description** | Lists revisions for a file. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |

**Output:** Returns revisions array (each with `revisionid`, `size`, `hash`, `created`) and file metadata.

**Errors:** `1000`, `1004`, `2000`, `2002`, `2003`, `2009`, `2010`, `4000`

---

### revertrevision

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/revertrevision` |
| **Description** | Reverts a file to a given revision. Current contents are saved as a new revision. |

**Required (use `fileid` OR `path`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `path` | string — file path |
| `revisionid` | int — revision ID to revert to |

**Output:** Returns new metadata of the file.

**Errors:** `1000`, `1004`, `2000`, `2002`, `2003`, `2009`, `2010`, `4000`, `5000`

---

## Newsletter

### newsletter_subscribe

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/newsletter_subscribe` |
| **Description** | Subscribes an email for the pCloud Newsletter. If the email was not already verified, a verification link is sent to that email. |

**Required:**

| Parameter | Description |
|---|---|
| `mail` | string — email to subscribe |

**Output:** Returns `verifymail` (bool — true if a verification mail was sent).

**Errors:** `1000`, `1033`, `2000`, `2018`, `5000`

---

### newsletter_check

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/newsletter_check` |
| **Description** | Checks if the currently logged-in user is subscribed to the pCloud Newsletter. |

**Output:** Returns `subscribed` (bool — true if subscribed) and `verified` (bool — true if the email has been verified).

**Errors:** `1000`, `2000`, `5000`

---

### newsletter_verifyemail

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/newsletter_verifyemail` |
| **Description** | Uses a code sent via email to verify the subscriber's email address. If the code is valid, the email is marked as verified. |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — verification code sent via email |

**Output:** Returns `email` (the email that was verified).

**Errors:** `1000`, `1022`, `2000`, `2012`, `2013`, `5000`

---

### newsletter_unsubscribe

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/newsletter_unsubscribe` |
| **Description** | Uses a code sent via email to unsubscribe the email from the Newsletter. Always returns `result=0` even if the user was never subscribed (for security reasons). |

**Required:**

| Parameter | Description |
|---|---|
| `code` | string — unsubscribe code sent via email |

**Errors:** `1000`, `1022`, `2000`, `2012`, `5000`

---

### newsletter_unsibscribemail

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/newsletter_unsibscribemail` |
| **Description** | Sends an email with a code that can be used to unsubscribe from the Newsletter. Always returns `result=0` even if the email was never subscribed (for security reasons). (Note: method name has a typo in the official API.) |

**Required:**

| Parameter | Description |
|---|---|
| `mail` | string — the subscribed email address |

**Errors:** `1000`, `1033`, `2000`, `2018`, `5000`

---

## Trash

### trash_list

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/trash_list` |
| **Description** | Lists the contents of a Trash folder. Root of Trash is `folderid=0`. Metadata includes `origparentfolderid` (original parent before deletion). Only files/folders belonging to the current user are shown. Similar to `listfolder`. |

**Optional:**

| Parameter | Description |
|---|---|
| `folderid` | int — Trash folder ID (default: 0 = root) |
| `nofiles` | int — exclude files, only folders |
| `recursive` | int — include subfolders recursively |

**Output:** Returns metadata with `contents` array.

**Errors:** `1000`, `1017`, `2000`, `2005`, `4000`, `5000`

---

### trash_restorepath

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/trash_restorepath` |
| **Description** | Calculates where a Trash item would be restored to. Ensures the destination has `ismine: true`. Generates new names on conflicts. |

**Required (use `fileid` OR `folderid`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `folderid` | int — folder ID |

**Output:** Returns `metadata` (how the item will look) and `destination` (calculated restore target).

**Errors:** `1000`, `1017`, `1018`, `1053`, `2000`, `2005`, `2009`, `4000`, `5000`

---

### trash_restore

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/trash_restore` |
| **Description** | Restores files or folders from the Trash. If `folderid=0`, restores all Trash contents. Restores until quota is exceeded, then raises an error. |

**Required (use `fileid` OR `folderid`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `folderid` | int — folder ID |

**Optional:**

| Parameter | Description |
|---|---|
| `restoreto` | int — destination folder ID |
| `metadata` | int — include folder contents in response |

**Output:** Returns metadata of the restored item.

**Errors:** `1000`, `1017`, `1018`, `1053`, `1054`, `2000`, `2003`, `2005`, `2008`, `2009`, `4000`, `5000`

---

### trash_clear

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/trash_clear` |
| **Description** | **Permanently** deletes files or folders from the Trash. Cannot be undone. If `folderid=0`, clears entire Trash. |

**Required (use `fileid` OR `folderid`):**

| Parameter | Description |
|---|---|
| `fileid` | int — file ID |
| `folderid` | int — folder ID |

**Errors:** `1000`, `1017`, `1018`, `1053`, `2000`, `2005`, `2009`, `4000`, `5000`

---

## Collection

### collection_list

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/collection_list` |
| **Description** | Lists the collections owned by the current user. System collections are generated on the first call to this method. Automatically removes items from collections that can no longer be found (e.g., moved to trash, unshared). |

**Optional:**

| Parameter | Description |
|---|---|
| `type` | int — filter by collection type (1 = playlists) |
| `showfiles` | int — if set, `contents` will be filled with file metadata |
| `pagesize` | int — if set with `showfiles`, limits items in `contents` to this count |

**Output:** Returns `collections` array. Each collection includes `id`, `name`, `type`, `ismine`, `items`, `system`, `created`, `modified`, and optionally `contents`.

**Errors:** `1000`, `2000`, `4000`, `5000`

---

### collection_details

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/collection_details` |
| **Description** | Returns details for a given collection and the items in it. Supports paging. Automatically removes items that can no longer be found (e.g., moved to trash, unshared). When paging, pages may have fewer results than `pagesize` while more pages remain available. |

**Required:**

| Parameter | Description |
|---|---|
| `collectionid` | int — collection ID |

**Optional:**

| Parameter | Description |
|---|---|
| `page` | int — page number (default 0 = all items) |
| `pagesize` | int — items per page |

**Output:** Returns `collection` with `contents` array. Each item includes standard metadata plus `position` and `added` fields.

**Errors:** `1000`, `1057`, `2000`, `2065`, `4000`, `5000`

---

### collection_create

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/collection_create` |
| **Description** | Creates a new collection for the current user. Optionally, files can be provided to pre-fill the collection. |

**Required:**

| Parameter | Description |
|---|---|
| `name` | string — name of the new collection |

**Optional:**

| Parameter | Description |
|---|---|
| `type` | int — type of collection (default 1 = playlist) |
| `fileids` | string — comma-separated list of file IDs to fill the collection |

**Output:** Returns `collection`. If files were provided, also returns `linkresult` (see `collection_linkfiles`). If linking was unsuccessful, `linkresult` will be `false`.

**Errors:** `1000`, `1039`, `1058`, `2000`, `2073`, `4000`, `5000`

---

### collection_rename

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/collection_rename` |
| **Description** | Renames a given collection owned by the current user. |

**Required:**

| Parameter | Description |
|---|---|
| `collectionid` | int — collection ID |
| `name` | string — new name for the collection |

**Output:** Returns the modified `collection`.

**Errors:** `1000`, `1039`, `1057`, `2000`, `2065`, `4000`, `5000`

---

### collection_delete

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/collection_delete` |
| **Description** | Deletes a given collection owned by the current user. System collections cannot be deleted (error `2065` will be raised). |

**Required:**

| Parameter | Description |
|---|---|
| `collectionid` | int — collection ID |

**Errors:** `1000`, `1057`, `2000`, `2065`, `4000`, `5000`

---

### collection_linkfiles

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/collection_linkfiles` |
| **Description** | Appends files to a collection. Files are added at the end; use `collection_move` to reorder afterwards. Preserves the relative order given in `fileids`. Duplicates are not allowed. |

**Required:**

| Parameter | Description |
|---|---|
| `collectionid` | int — collection ID |
| `fileids` | string — comma-separated list of file IDs to add |

**Optional:**

| Parameter | Description |
|---|---|
| `noitems` | int — if set, `linkresult` will be empty |

**Output:** Returns the updated `collection` and `linkresult` array. Each entry in `linkresult` contains `result` (0 = success), `fileid`, optionally `message` (on error), and `metadata` (on success, with added `position` and `added` fields).

**Errors:** `1000`, `1038`, `1057`, `2000`, `2009`, `2065`, `2071`, `2072`, `2073`, `4000`, `5000`

---

### collection_unlinkfiles

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/collection_unlinkfiles` |
| **Description** | Removes files from a collection. Three methods: by `positions` (comma-separated), by `fileids` (comma-separated), or `all`. Priority order: `positions` > `all` > `fileids`. |

**Required:**

| Parameter | Description |
|---|---|
| `collectionid` | int — collection ID |

**Optional (use one):**

| Parameter | Description |
|---|---|
| `all` | int — if set, unlink all files |
| `positions` | string — comma-separated list of positions to unlink |
| `fileids` | string — comma-separated list of file IDs to unlink |

**Output:** Returns the modified `collection`.

**Errors:** `1000`, `1038`, `1057`, `2000`, `2065`, `4000`, `5000`

---

### collection_move

| | |
|---|---|
| **Auth** | Yes |
| **URL** | `https://api.pcloud.com/collection_move` |
| **Description** | Changes the position of an item in a given collection owned by the current user. |

**Required:**

| Parameter | Description |
|---|---|
| `collectionid` | int — collection ID |
| `item` | int — current position of the item |
| `fileid` | int — file ID of the item to move |
| `position` | int — target position |

**Errors:** `1000`, `1057`, `1059`, `1060`, `2000`, `2065`, `2066`, `4000`, `5000`

---

## OAuth 2.0

### authorize

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://my.pcloud.com/oauth2/authorize` |
| **Description** | Initiates the OAuth 2.0 authorization flow. The user is redirected to pCloud to grant permissions, then redirected back to your app with an authorization code. Use `response_type=code` for the authorization code grant. The `locationid` parameter in the response indicates which API server to use (1 = US, 2 = EU). |

**Parameters:**

| Parameter | Description |
|---|---|
| `client_id` | string — your app's client ID |
| `redirect_uri` | string — your registered redirect URI |
| `response_type` | string — `code` for authorization code |

---

### oauth2_token

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/oauth2_token` |
| **Description** | Exchanges an authorization code for an access token. |

**Required:**

| Parameter | Description |
|---|---|
| `client_id` | string — your app's client ID |
| `client_secret` | string — your app's client secret |
| `code` | string — authorization code from the authorize step |

**Output:** Returns `access_token`, `token_type`, `userid`, `locationid`.

---

## Transfer

### uploadtransfer

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/uploadtransfer` |
| **Description** | Uploads file(s) as a transfer — creates and sends transfer download links to the specified receiver email(s). |

**Required:**

| Parameter | Description |
|---|---|
| `sendermail` | string — email of the sender |
| `receivermails` | string — email(s) of receivers (up to 20), comma-separated |

**Optional:**

| Parameter | Description |
|---|---|
| `message` | string — short message/comment to receivers (up to 160 characters) |
| `progresshash` | string — hash for monitoring progress via `uploadtransferprogress` |

**Errors:** `1074`, `1075`, `2001`, `2041`, `2088`, `2097`, `2098`, `2099`, `2100`, `5000`, `5001`

---

### uploadtransferprogress

| | |
|---|---|
| **Auth** | No |
| **URL** | `https://api.pcloud.com/uploadtransferprogress` |
| **Description** | Monitors the progress of a file transfer initiated by `uploadtransfer`. |

**Required:**

| Parameter | Description |
|---|---|
| `progresshash` | string — the same hash sent to `uploadtransfer` |

**Output:** Returns the same data as `uploadprogress`.

**Errors:** `1052`, `1902`

---

## Common Error Codes

| Code | Description |
|---|---|
| `1000` | Log in required. |
| `2000` | Log in failed. |
| `4000` | Too many login tries from this IP address. |
| `5000` | Internal error. Try again later. |
| `5001` | Internal upload error. |
| `5002` | Internal error, no servers available. Try again later. |
| `7001` | Invalid link code. |
| `7002` | Link deleted by owner. |
| `7004` | Link has expired. |
| `7005` | Link has reached its traffic limit. |
| `7006` | Link has reached maximum downloads. |
| `7007` | Upload link has reached its space limit. |
| `7008` | Upload link has reached its file limit. |
| `7009` | Archive is password protected — supply `password`. |