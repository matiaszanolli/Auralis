#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Advanced Search Interface
~~~~~~~~~~~~~~~~~~~~~~~~~

Sophisticated search and filtering capabilities for the music library
with audio analysis criteria and metadata filtering.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import Dict, List, Optional, Callable, Any
import json
from datetime import datetime, timedelta


class SearchCriteriaRow(ctk.CTkFrame):
    """Individual search criteria row widget"""

    def __init__(self, master, remove_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.remove_callback = remove_callback

        self.setup_ui()

    def setup_ui(self):
        """Setup criteria row UI"""
        # Logic operator (AND/OR) - only shown for non-first rows
        self.logic_var = ctk.StringVar(value="AND")
        self.logic_menu = ctk.CTkOptionMenu(
            self, variable=self.logic_var, width=60,
            values=["AND", "OR"]
        )
        # Initially hidden - will be shown for subsequent rows
        # self.logic_menu.pack(side="left", padx=(0, 5))

        # Field selection
        self.field_var = ctk.StringVar(value="Title")
        self.field_menu = ctk.CTkOptionMenu(
            self, variable=self.field_var, width=120,
            values=[
                "Title", "Artist", "Album", "Genre", "Year",
                "Duration", "File Format", "Sample Rate", "Bit Depth",
                "Play Count", "Last Played", "Date Added", "Favorite",
                "Peak Level", "RMS Level", "DR Rating", "LUFS",
                "Mastering Quality", "File Size", "File Path"
            ],
            command=self._on_field_change
        )
        self.field_menu.pack(side="left", padx=(0, 5))

        # Operator selection
        self.operator_var = ctk.StringVar(value="contains")
        self.operator_menu = ctk.CTkOptionMenu(
            self, variable=self.operator_var, width=100,
            values=["contains", "is", "is not", "starts with", "ends with"]
        )
        self.operator_menu.pack(side="left", padx=(0, 5))

        # Value entry/selection
        self.value_widget = ctk.CTkEntry(self, placeholder_text="Enter value", width=200)
        self.value_widget.pack(side="left", padx=(0, 5))

        # Remove button
        self.remove_btn = ctk.CTkButton(
            self, text="✕", width=30, height=30,
            command=self._remove_criteria
        )
        self.remove_btn.pack(side="right", padx=(5, 0))

        # Update operators based on initial field
        self._on_field_change("Title")

    def _on_field_change(self, field):
        """Update operators based on selected field"""
        numeric_fields = [
            "Year", "Duration", "Sample Rate", "Bit Depth", "Play Count",
            "Peak Level", "RMS Level", "DR Rating", "LUFS",
            "Mastering Quality", "File Size"
        ]

        boolean_fields = ["Favorite"]

        date_fields = ["Last Played", "Date Added"]

        if field in numeric_fields:
            operators = ["=", "≠", ">", "<", "≥", "≤", "between"]
            self.operator_menu.configure(values=operators)
            self.operator_var.set("=")

            # Update value widget for numeric input
            self._update_value_widget("number")

        elif field in boolean_fields:
            operators = ["is", "is not"]
            self.operator_menu.configure(values=operators)
            self.operator_var.set("is")

            # Update value widget for boolean selection
            self._update_value_widget("boolean")

        elif field in date_fields:
            operators = ["is", "after", "before", "within last"]
            self.operator_menu.configure(values=operators)
            self.operator_var.set("after")

            # Update value widget for date input
            self._update_value_widget("date")

        elif field == "Genre":
            operators = ["is", "is not", "contains", "is any of"]
            self.operator_menu.configure(values=operators)
            self.operator_var.set("is")

            # Update value widget for genre selection
            self._update_value_widget("genre")

        elif field == "File Format":
            operators = ["is", "is not", "is any of"]
            self.operator_menu.configure(values=operators)
            self.operator_var.set("is")

            # Update value widget for format selection
            self._update_value_widget("format")

        else:
            # Text fields
            operators = ["contains", "is", "is not", "starts with", "ends with", "matches regex"]
            self.operator_menu.configure(values=operators)
            self.operator_var.set("contains")

            # Update value widget for text input
            self._update_value_widget("text")

    def _update_value_widget(self, widget_type):
        """Update the value input widget based on type"""
        # Remove existing value widget
        self.value_widget.destroy()

        if widget_type == "boolean":
            self.value_widget = ctk.CTkOptionMenu(
                self, width=200,
                values=["True", "False"]
            )

        elif widget_type == "genre":
            # TODO: Get genres from database
            self.value_widget = ctk.CTkComboBox(
                self, width=200,
                values=["Rock", "Pop", "Jazz", "Classical", "Electronic", "Hip-Hop", "Folk", "Country"]
            )

        elif widget_type == "format":
            self.value_widget = ctk.CTkOptionMenu(
                self, width=200,
                values=["MP3", "FLAC", "WAV", "OGG", "M4A", "AAC", "WMA"]
            )

        elif widget_type == "date":
            date_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.value_widget = date_frame

            # Date input options
            self.date_option_var = ctk.StringVar(value="days")
            date_option = ctk.CTkOptionMenu(
                date_frame, variable=self.date_option_var, width=80,
                values=["days", "weeks", "months", "years"]
            )
            date_option.pack(side="left")

            self.date_value = ctk.CTkEntry(date_frame, width=60, placeholder_text="7")
            self.date_value.pack(side="left", padx=(5, 0))

        elif widget_type == "number":
            number_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.value_widget = number_frame

            self.number_value = ctk.CTkEntry(number_frame, width=100, placeholder_text="Value")
            self.number_value.pack(side="left")

            # For "between" operator, add second value
            self.number_value2 = ctk.CTkEntry(number_frame, width=100, placeholder_text="Max")
            # Initially hidden

        else:  # text
            self.value_widget = ctk.CTkEntry(self, placeholder_text="Enter value", width=200)

        self.value_widget.pack(side="left", padx=(0, 5), before=self.remove_btn)

    def _remove_criteria(self):
        """Remove this criteria row"""
        if self.remove_callback:
            self.remove_callback(self)

    def get_criteria(self):
        """Get the search criteria from this row"""
        field = self.field_var.get()
        operator = self.operator_var.get()

        # Get value based on widget type
        if isinstance(self.value_widget, ctk.CTkEntry):
            value = self.value_widget.get().strip()
        elif isinstance(self.value_widget, (ctk.CTkOptionMenu, ctk.CTkComboBox)):
            value = self.value_widget.get()
        elif hasattr(self.value_widget, 'winfo_children'):  # Frame with multiple inputs
            if hasattr(self, 'date_value'):
                value = f"{self.date_value.get()} {self.date_option_var.get()}"
            elif hasattr(self, 'number_value'):
                if operator == "between" and hasattr(self, 'number_value2'):
                    value = f"{self.number_value.get()}-{self.number_value2.get()}"
                else:
                    value = self.number_value.get()
            else:
                value = ""
        else:
            value = ""

        return {
            'logic': self.logic_var.get(),
            'field': field,
            'operator': operator,
            'value': value
        }

    def set_logic_visible(self, visible):
        """Show or hide the logic operator"""
        if visible:
            self.logic_menu.pack(side="left", padx=(0, 5), before=self.field_menu)
        else:
            self.logic_menu.pack_forget()


class AdvancedSearchWindow(ctk.CTkToplevel):
    """Advanced search interface window"""

    def __init__(self, parent, library_manager=None, callback=None):
        super().__init__(parent)
        self.library_manager = library_manager
        self.callback = callback
        self.criteria_rows = []

        self.title("Advanced Search")
        self.geometry("800x600")
        self.resizable(True, True)

        self.setup_ui()

    def setup_ui(self):
        """Setup advanced search UI"""
        # Header
        header = ctk.CTkLabel(self, text="🔍 Advanced Search",
                            font=ctk.CTkFont(size=18, weight="bold"))
        header.pack(pady=10)

        # Search criteria section
        criteria_label = ctk.CTkLabel(self, text="Search Criteria:",
                                    font=ctk.CTkFont(size=14, weight="bold"))
        criteria_label.pack(anchor="w", padx=20, pady=(20, 5))

        # Criteria container
        self.criteria_frame = ctk.CTkScrollableFrame(self, height=300)
        self.criteria_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Add criteria button
        add_btn = ctk.CTkButton(self, text="+ Add Criteria", command=self._add_criteria)
        add_btn.pack(pady=5)

        # Search options section
        options_frame = ctk.CTkFrame(self, fg_color="transparent")
        options_frame.pack(fill="x", padx=20, pady=10)

        # Left side - Search scope
        scope_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        scope_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(scope_frame, text="Search in:",
                    font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")

        self.scope_var = ctk.StringVar(value="All Library")
        scope_options = ctk.CTkFrame(scope_frame, fg_color="transparent")
        scope_options.pack(anchor="w", pady=5)

        for scope in ["All Library", "Current Playlist", "Selected Tracks"]:
            radio = ctk.CTkRadioButton(scope_options, text=scope,
                                     variable=self.scope_var, value=scope)
            radio.pack(side="left", padx=(0, 15))

        # Right side - Result options
        result_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        result_frame.pack(side="right")

        ctk.CTkLabel(result_frame, text="Results:",
                    font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")

        result_options = ctk.CTkFrame(result_frame, fg_color="transparent")
        result_options.pack(anchor="w", pady=5)

        self.limit_var = ctk.BooleanVar(value=True)
        limit_check = ctk.CTkCheckBox(result_options, text="Limit to", variable=self.limit_var)
        limit_check.pack(side="left")

        self.limit_entry = ctk.CTkEntry(result_options, width=60, placeholder_text="1000")
        self.limit_entry.pack(side="left", padx=(5, 0))
        self.limit_entry.insert(0, "1000")

        ctk.CTkLabel(result_options, text="results").pack(side="left", padx=(5, 0))

        # Sorting section
        sort_frame = ctk.CTkFrame(self, fg_color="transparent")
        sort_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(sort_frame, text="Sort results by:",
                    font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        self.sort_var = ctk.StringVar(value="Relevance")
        sort_menu = ctk.CTkOptionMenu(
            sort_frame, variable=self.sort_var, width=150,
            values=["Relevance", "Title", "Artist", "Album", "Year", "Duration",
                   "Play Count", "Date Added", "Mastering Quality"]
        )
        sort_menu.pack(side="left", padx=(10, 5))

        self.sort_order_var = ctk.StringVar(value="Ascending")
        order_menu = ctk.CTkOptionMenu(
            sort_frame, variable=self.sort_order_var, width=100,
            values=["Ascending", "Descending"]
        )
        order_menu.pack(side="left", padx=5)

        # Saved searches section
        saved_frame = ctk.CTkFrame(self, fg_color="transparent")
        saved_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(saved_frame, text="Saved Searches:",
                    font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        self.saved_var = ctk.StringVar(value="Select saved search...")
        saved_menu = ctk.CTkOptionMenu(
            saved_frame, variable=self.saved_var, width=200,
            values=["Select saved search...", "Recent high-quality tracks", "Unplayed favorites"],
            command=self._load_saved_search
        )
        saved_menu.pack(side="left", padx=(10, 5))

        save_btn = ctk.CTkButton(saved_frame, text="Save Current", width=100,
                               command=self._save_search)
        save_btn.pack(side="left", padx=5)

        # Preview section
        preview_frame = ctk.CTkFrame(self)
        preview_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(preview_frame, text="Search Preview:",
                    font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))

        self.preview_label = ctk.CTkLabel(
            preview_frame, text="Add criteria to see search preview",
            font=ctk.CTkFont(size=11), text_color="#888888",
            wraplength=600, justify="left"
        )
        self.preview_label.pack(anchor="w", padx=10, pady=(0, 10))

        # Buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=20)

        cancel_btn = ctk.CTkButton(button_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side="right", padx=(5, 0))

        search_btn = ctk.CTkButton(button_frame, text="Search", command=self._execute_search)
        search_btn.pack(side="right")

        clear_btn = ctk.CTkButton(button_frame, text="Clear All", command=self._clear_all)
        clear_btn.pack(side="left")

        # Add initial criteria row
        self._add_criteria()

    def _add_criteria(self):
        """Add a new search criteria row"""
        criteria_row = SearchCriteriaRow(self.criteria_frame, remove_callback=self._remove_criteria)
        criteria_row.pack(fill="x", pady=2)

        # Show logic operator for non-first rows
        if len(self.criteria_rows) > 0:
            criteria_row.set_logic_visible(True)

        self.criteria_rows.append(criteria_row)
        self._update_preview()

    def _remove_criteria(self, criteria_row):
        """Remove a criteria row"""
        if criteria_row in self.criteria_rows:
            self.criteria_rows.remove(criteria_row)
            criteria_row.destroy()

            # Hide logic operator for first row if it exists
            if self.criteria_rows:
                self.criteria_rows[0].set_logic_visible(False)

            self._update_preview()

    def _clear_all(self):
        """Clear all search criteria"""
        for row in self.criteria_rows:
            row.destroy()
        self.criteria_rows = []
        self._add_criteria()  # Add one empty row

    def _update_preview(self):
        """Update the search preview text"""
        if not self.criteria_rows:
            self.preview_label.configure(text="Add criteria to see search preview")
            return

        preview_parts = []
        for i, row in enumerate(self.criteria_rows):
            criteria = row.get_criteria()
            if criteria['value']:
                if i > 0:
                    preview_parts.append(criteria['logic'])

                field = criteria['field']
                operator = criteria['operator']
                value = criteria['value']

                # Format based on operator
                if operator in ["contains", "starts with", "ends with"]:
                    part = f"{field} {operator} '{value}'"
                elif operator == "is any of":
                    part = f"{field} is one of [{value}]"
                elif operator == "between":
                    part = f"{field} is between {value}"
                elif operator == "within last":
                    part = f"{field} is within last {value}"
                else:
                    part = f"{field} {operator} {value}"

                preview_parts.append(part)

        if preview_parts:
            preview_text = " ".join(preview_parts)
            self.preview_label.configure(text=preview_text)
        else:
            self.preview_label.configure(text="Enter values to see search preview")

    def _load_saved_search(self, selection):
        """Load a saved search"""
        if selection == "Select saved search...":
            return

        # Clear current criteria
        self._clear_all()

        # Load predefined searches
        if selection == "Recent high-quality tracks":
            # Add criteria for high quality tracks from last 30 days
            self.criteria_rows[0].field_var.set("Date Added")
            self.criteria_rows[0]._on_field_change("Date Added")
            self.criteria_rows[0].operator_var.set("within last")
            if hasattr(self.criteria_rows[0], 'date_value'):
                self.criteria_rows[0].date_value.insert(0, "30")
                self.criteria_rows[0].date_option_var.set("days")

            self._add_criteria()
            self.criteria_rows[1].field_var.set("Mastering Quality")
            self.criteria_rows[1]._on_field_change("Mastering Quality")
            self.criteria_rows[1].operator_var.set("≥")
            if hasattr(self.criteria_rows[1], 'number_value'):
                self.criteria_rows[1].number_value.insert(0, "0.8")

        elif selection == "Unplayed favorites":
            # Add criteria for favorite tracks with 0 plays
            self.criteria_rows[0].field_var.set("Favorite")
            self.criteria_rows[0]._on_field_change("Favorite")
            self.criteria_rows[0].operator_var.set("is")

            self._add_criteria()
            self.criteria_rows[1].field_var.set("Play Count")
            self.criteria_rows[1]._on_field_change("Play Count")
            self.criteria_rows[1].operator_var.set("=")
            if hasattr(self.criteria_rows[1], 'number_value'):
                self.criteria_rows[1].number_value.insert(0, "0")

        self._update_preview()

    def _save_search(self):
        """Save current search criteria"""
        # TODO: Implement search saving
        messagebox.showinfo("Save Search", "Search saving feature coming soon!")

    def _execute_search(self):
        """Execute the search with current criteria"""
        if not self.criteria_rows:
            messagebox.showwarning("No Criteria", "Please add at least one search criteria")
            return

        # Collect all criteria
        search_criteria = []
        for row in self.criteria_rows:
            criteria = row.get_criteria()
            if criteria['value']:
                search_criteria.append(criteria)

        if not search_criteria:
            messagebox.showwarning("No Values", "Please enter values for your search criteria")
            return

        # Build search parameters
        search_params = {
            'criteria': search_criteria,
            'scope': self.scope_var.get(),
            'sort_by': self.sort_var.get(),
            'sort_order': self.sort_order_var.get(),
            'limit': int(self.limit_entry.get()) if self.limit_var.get() else None
        }

        # Execute search via callback
        if self.callback:
            self.callback(search_params)

        # Close window
        self.destroy()


class QuickSearchBar(ctk.CTkFrame):
    """Quick search bar with filters and shortcuts"""

    def __init__(self, master, callback_manager=None, **kwargs):
        super().__init__(master, **kwargs)
        self.callback_manager = callback_manager

        self.setup_ui()

    def setup_ui(self):
        """Setup quick search bar UI"""
        # Search entry
        self.search_entry = ctk.CTkEntry(
            self, placeholder_text="🔍 Quick search...",
            width=300, height=35
        )
        self.search_entry.pack(side="left", padx=(10, 5))
        self.search_entry.bind('<KeyRelease>', self._on_search)
        self.search_entry.bind('<Return>', self._on_enter)

        # Quick filters
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(side="left", padx=10)

        # Filter buttons
        self.filter_buttons = {}
        filters = [
            ("All", "all"),
            ("❤️", "favorites"),
            ("⭐", "high_quality"),
            ("🆕", "recent"),
            ("🎵", "unplayed")
        ]

        for text, filter_type in filters:
            btn = ctk.CTkButton(
                filter_frame, text=text, width=40, height=30,
                command=lambda f=filter_type: self._apply_filter(f)
            )
            btn.pack(side="left", padx=1)
            self.filter_buttons[filter_type] = btn

        # Advanced search button
        advanced_btn = ctk.CTkButton(
            self, text="Advanced", width=80, height=30,
            command=self._show_advanced_search
        )
        advanced_btn.pack(side="right", padx=10)

        # Initially select "All" filter
        self._apply_filter("all")

    def _on_search(self, event=None):
        """Handle search input"""
        query = self.search_entry.get().strip()
        if self.callback_manager:
            self.callback_manager('quick_search', query)

    def _on_enter(self, event=None):
        """Handle Enter key in search"""
        query = self.search_entry.get().strip()
        if query and self.callback_manager:
            self.callback_manager('search_execute', query)

    def _apply_filter(self, filter_type):
        """Apply quick filter"""
        # Update button appearance
        for ftype, btn in self.filter_buttons.items():
            if ftype == filter_type:
                btn.configure(fg_color="#1F538D")
            else:
                btn.configure(fg_color="#565b5e")

        if self.callback_manager:
            self.callback_manager('filter_applied', filter_type)

    def _show_advanced_search(self):
        """Show advanced search dialog"""
        if self.callback_manager:
            self.callback_manager('show_advanced_search')

    def set_search_text(self, text):
        """Set the search text"""
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, text)

    def clear_search(self):
        """Clear the search text"""
        self.search_entry.delete(0, tk.END)
        self._apply_filter("all")