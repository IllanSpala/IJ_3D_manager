import customtkinter as ctk

app = ctk.CTk()
app.geometry("800x600")

main = ctk.CTkFrame(app)
main.pack(fill="both", expand=True)

# Test Grid layout
tab = ctk.CTkFrame(main)
tab.pack(fill="both", expand=True)

tab.rowconfigure(0, weight=0)
tab.rowconfigure(1, weight=1)
tab.columnconfigure(0, weight=1)

top = ctk.CTkFrame(tab, fg_color="red", height=100)
top.grid(row=0, column=0, sticky="new")
# Force top frame height to not collapse if empty
top.pack_propagate(False)

bottom = ctk.CTkFrame(tab, fg_color="blue")
bottom.grid(row=1, column=0, sticky="nsew")

app.after(1000, lambda: print(top.winfo_y(), bottom.winfo_y(), bottom.winfo_height()))
app.after(1500, app.destroy)
app.mainloop()
