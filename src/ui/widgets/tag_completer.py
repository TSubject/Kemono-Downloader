from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
from PyQt5.QtWidgets import QCompleter, QLineEdit

from ...core.tag_matcher import TagSearchIndex, compact_search_text


class TagMultiCompleter(QCompleter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_prefix = ""

    def pathFromIndex(self, index):
        path = super().pathFromIndex(index)
        return f"{self.current_prefix}{path}"

    def splitPath(self, path):
        # Return an empty prefix so Qt's internal proxy model does NOT
        # re-filter the results that TagSearchIndex already pre-filtered.
        # Without this, acronym / hangul-initial matches (e.g. "bh" -> "black_hair")
        # are silently removed by Qt's MatchContains pass because the token is
        # not literally a substring of the matched tag.
        return [""]

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Down:
                if self.popup() and self.popup().isVisible():
                    return self._accept_current_and_prepare_next()
        return super().eventFilter(obj, event)

    def _accept_current_and_prepare_next(self):
        popup = self.popup()
        current_index = popup.currentIndex()
        if not current_index.isValid():
            current_index = self.completionModel().index(0, 0)

        selected_text = self.completionModel().data(current_index)
        if not selected_text:
            return False

        line_edit = self.widget()
        new_locked_text = f"{self.current_prefix}{selected_text}, "
        self.current_prefix = new_locked_text

        next_row = current_index.row() + 1
        if next_row < self.completionModel().rowCount():
            next_index = self.completionModel().index(next_row, 0)
            popup.setCurrentIndex(next_index)
            next_text = self.completionModel().data(next_index)
            self._set_line_edit_text(line_edit, f"{new_locked_text}{next_text}")
        else:
            self._set_line_edit_text(line_edit, new_locked_text)

        return True

    @staticmethod
    def _set_line_edit_text(line_edit, text):
        line_edit.blockSignals(True)
        line_edit.setText(text)
        line_edit.setCursorPosition(len(text))
        line_edit.blockSignals(False)


class TagCompleterController(QObject):
    def __init__(
        self,
        line_edit: QLineEdit,
        tags=None,
        parent=None,
        limit: int = 40,
        debounce_ms: int = 120,
        min_chars: int = 1,
    ):
        super().__init__(parent or line_edit)
        self.line_edit = line_edit
        self.limit = limit
        self.min_chars = min_chars
        self.debounce_ms = debounce_ms
        self.index = TagSearchIndex(tags or [])

        self.completer = TagMultiCompleter([], self)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setMaxVisibleItems(15)
        self.completer.setWrapAround(False)
        self.line_edit.setCompleter(self.completer)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.update_completions)
        self.line_edit.textEdited.connect(self.on_text_edited)

        # Install on the line edit so we can intercept Tab before Qt moves focus.
        self.line_edit.installEventFilter(self)

    # ------------------------------------------------------------------
    # Event filter – Tab key accepts the top suggestion
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self.line_edit and event.type() == QEvent.KeyPress:
            popup = self.completer.popup()
            if popup and popup.isVisible() and event.key() == Qt.Key_Tab:
                self._accept_top_completion()
                return True  # consume Tab so keyboard focus stays here
        return super().eventFilter(obj, event)

    def _accept_top_completion(self):
        """Accept the highlighted (or first) suggestion and append ', ' ready for the next tag."""
        popup = self.completer.popup()
        model = self.completer.completionModel()

        current_index = popup.currentIndex()
        if not current_index.isValid():
            current_index = model.index(0, 0)
        if not current_index.isValid():
            return

        selected = model.data(current_index)
        if not selected:
            return

        new_text = f"{self.completer.current_prefix}{selected}, "
        self.completer.current_prefix = new_text
        TagMultiCompleter._set_line_edit_text(self.line_edit, new_text)
        popup.hide()

        # Restart debounce so completions for the next token appear automatically.
        self.timer.start(self.debounce_ms)

    # ------------------------------------------------------------------

    def set_tags(self, tags, favorite_tags=None):
        self.index.set_tags(tags or [], favorite_tags=favorite_tags)
        self.update_completions()

    def on_text_edited(self, text):
        self.completer.current_prefix = self._current_prefix(text)
        self.timer.start(self.debounce_ms)

    def update_completions(self):
        token = self._current_token(self.line_edit.text())
        search_text = token.lstrip("-").strip()
        if len(compact_search_text(search_text)) < self.min_chars:
            self.completer.model().setStringList([])
            return

        matches = self.index.search(search_text, limit=self.limit)
        self.completer.model().setStringList(matches)
        if matches:
            self.completer.complete()

    @staticmethod
    def _current_token(text):
        return (text or "").split(",")[-1].strip()

    @staticmethod
    def _current_prefix(text):
        value = text or ""
        if "," in value:
            prefix = value[: value.rfind(",") + 1]
            if not prefix.endswith(" "):
                prefix += " "
        else:
            prefix = ""

        token = value.split(",")[-1].lstrip()
        if token.startswith("-"):
            prefix += "-"
        return prefix


def install_tag_completer(line_edit: QLineEdit, tags=None, parent=None, **kwargs):
    return TagCompleterController(line_edit, tags=tags, parent=parent, **kwargs)
