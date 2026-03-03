/**
 * SearchKeyboardHint - Keyboard shortcut help text
 *
 * Shows hint for keyboard shortcuts (/, ⌘K) when search is empty
 */

interface SearchKeyboardHintProps {
  show: boolean;
}

export const SearchKeyboardHint = ({ show: _show }: SearchKeyboardHintProps) => {
  // Hide keyboard hint to reduce visual noise - search should feel ambient
  return null;
};

export default SearchKeyboardHint;
