# Export delivery and VPS cleanup

User decision, 14 October 2026: once a finished video has been transferred and verified on the owner's PC, delete its final MP4 from the VPS as well as obsolete production files. Do not keep the server as the permanent video archive.

Delivery must finish before cleanup. Record the project ID, exact server-relative path, file size and SHA-256 of each final export. Transfer to the agreed local episode folder; independently calculate the local size and SHA-256 and compare both with the server. An HTTP success, an existing filename or a completed download alone is insufficient. Complete render validation and actual visual inspection before marking the delivery verified.

Cleanup is scoped to the delivered projects and exact known temporary files. Check that no generation, render, export or download is still using a candidate. Resolve each candidate against its intended project or temporary root; reject paths outside that root, symlinks and unexpected replacements. Recheck its recorded size and hash immediately before deletion. Preserve application code, configuration, credentials, other projects and shared data.

Keep channel presets, character references, location masters, selected views, object and pose references, authored prompts, scripts, original voiceovers, transcripts and timestamps. A shot image used as an ordered pose reference is a required asset: do not purge it with obsolete frames. Keep compact generation/review receipts and a cleanup audit. Once delivered, obsolete unreferenced renders, rejected image versions, worker output duplicates and owned QA archives may be removed. Never apply a blanket recursive delete to the data volume or all projects.

Record delivery and deletion in project metadata so the site and subsequent agents know that the final export was transferred and removed. Do not leave a deleted MP4 presented as an available download or automatically restart production because its file is absent. Report disk space before and after cleanup and the exact files/bytes removed. A failed verification leaves the server copy intact; a cleanup failure remains a visible pending task, not a claimed success.

This is the required handoff procedure. It does not by itself install an automatic retention scheduler or authorize deleting undelivered videos. For the current fictional-life rebuild, apply it to both delivered episodes after their local exports have passed verification.
