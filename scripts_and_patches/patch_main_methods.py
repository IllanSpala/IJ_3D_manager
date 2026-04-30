import re

with open("app.py", "r") as f:
    code = f.read()

def patch_method(match):
    m_name = match.group(1)
    cls_name = match.group(2)
    return f'''    def {m_name}(self):
        self.clear_main()
        self.current_frame = {cls_name}(self.main_frame)
        self.current_frame.pack(side="top", fill="both", expand=True)
'''

# The previous logic was `self.current_frame.pack(fill="both", expand=True)`. This does side="top" but implicitly.
# If I change it to NOT expand=True, then it will stick to the top!
# BUT if it doesn't expand, the scroll frame inside won't expand!

# The ONLY SUREFIRE WAY to not center is to pack the Tab without expand, BUT make the main window NOT expand its frames.
# No, the foolproof way is pack_propagate(False) or place().
# Actually, place(relx=0, rely=0, relwidth=1, relheight=1) is the ultimate fix for all layout bugs in CustomTkinter.

code = re.sub(r'    def (show_\w+)\(self\):\n        self\.clear_main\(\)\n        self\.current_frame = (Tab\w+)\(self\.main_frame\)\n        self\.current_frame\.pack\(fill="both", expand=True\)', 
              r'    def \1(self):\n        self.clear_main()\n        self.current_frame = \2(self.main_frame)\n        self.current_frame.place(relx=0, rely=0, relwidth=1, relheight=1)', code)

with open("app.py", "w") as f:
    f.write(code)

