Bandcamp artist downloader
--------------------------

Download all free releases of a Bandcamp artist. 

This is proof-of-concept software for educational purposes.
I am not responsible for unwise use of this program nor the underlying library.


Requirements
------------
- email (for getting download receipts) 
  (^ PROGRAM WILL WIPE OLD EMAILS (read notice above)
- Python >= 3.11 (might work on earlier versions, but not tested)
- Python Poetry


Installation
------------
Install deps through Poetry. 
Installation by other means is possible but not supported.


Quickstart
----------
1. Find the artist subdomain example: 
   example: haircutsformen.bandcamp.com -> haircutsformen
2. Write your password to a file, here referred to '/run/secrets/mailpass'
3. Finally, run the command:
   python src/main.py haircutsformen johndoe@example.com /run/secrets/mailpass
4. Done.


Gotchas
-------
- Your mail server might require custom connection configration.
  Should be easy to hack it in yourself if needed.
  Works out-of-the-box with Dovecot, which is what the author recommends.
- Excessive usage can and will get you ratelimited.
- If the software slows your computer to a crawl, it's probably using too many
  unzipping workers, as that is the CPU-heavy part of the process. 
  Lower it with the --max-unzip-workers option.


License
-------
This software is licensed under the GNU AGPLv3. See LICENSE for more information. 

© 2023 Emanuel Johnson Godin



