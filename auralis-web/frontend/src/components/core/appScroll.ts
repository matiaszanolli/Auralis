/**
 * The id of the app's one scroll container, rendered by AppMainContent (#6631).
 *
 * Library views virtualize against it and react-infinite-scroll-component targets it by id, so the
 * id is named once here rather than spelled as a string literal at each reader.
 */
export const APP_MAIN_SCROLL_ID = 'app-main-content-scroll';
