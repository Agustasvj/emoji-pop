#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>

#include "cosmic-toplevel-info-client.h"
#include "cosmic-toplevel-management-client.h"

/* Dummy interface symbols required by generated scanner code */
const struct wl_interface ext_foreign_toplevel_handle_v1_interface = {
    "ext_foreign_toplevel_handle_v1", 1, 0, NULL, 0, NULL
};
const struct wl_interface zcosmic_workspace_handle_v1_interface = {
    "zcosmic_workspace_handle_v1", 1, 0, NULL, 0, NULL
};
const struct wl_interface ext_workspace_handle_v1_interface = {
    "ext_workspace_handle_v1", 1, 0, NULL, 0, NULL
};

struct ToplevelInfo {
    struct zcosmic_toplevel_handle_v1 *handle;
    char app_id[128];
    char title[256];
    int is_active;
    struct ToplevelInfo *next;
};

static struct wl_display *g_display = NULL;
static struct wl_registry *g_registry = NULL;
static struct wl_seat *g_seat = NULL;
static struct zcosmic_toplevel_info_v1 *g_info = NULL;
static struct zcosmic_toplevel_manager_v1 *g_manager = NULL;

static struct ToplevelInfo *g_list = NULL;
static struct zcosmic_toplevel_handle_v1 *g_last_active_handle = NULL;
static char g_last_active_app_id[128] = {0};
static char g_last_active_title[256] = {0};

static struct ToplevelInfo *get_or_create(struct zcosmic_toplevel_handle_v1 *handle) {
    for (struct ToplevelInfo *cur = g_list; cur; cur = cur->next) {
        if (cur->handle == handle) return cur;
    }
    struct ToplevelInfo *n = calloc(1, sizeof(struct ToplevelInfo));
    n->handle = handle;
    n->next = g_list;
    g_list = n;
    return n;
}

static void on_title(void *data, struct zcosmic_toplevel_handle_v1 *handle, const char *title) {
    struct ToplevelInfo *n = get_or_create(handle);
    if (title) strncpy(n->title, title, sizeof(n->title) - 1);
}

static void on_app_id(void *data, struct zcosmic_toplevel_handle_v1 *handle, const char *app_id) {
    struct ToplevelInfo *n = get_or_create(handle);
    if (app_id) strncpy(n->app_id, app_id, sizeof(n->app_id) - 1);
}

static void on_state(void *data, struct zcosmic_toplevel_handle_v1 *handle, struct wl_array *state) {
    struct ToplevelInfo *n = get_or_create(handle);
    uint32_t *entry;
    n->is_active = 0;
    wl_array_for_each(entry, state) {
        if (*entry == ZCOSMIC_TOPLEVEL_HANDLE_V1_STATE_ACTIVATED) {
            n->is_active = 1;
        }
    }
    if (n->is_active) {
        // Exclude Emoji Pop itself so we only track user application windows
        if (!strstr(n->app_id, "EmojiPop") && !strstr(n->app_id, "emoji-pop") &&
            !strstr(n->title, "Emoji Pop")) {
            g_last_active_handle = handle;
            strncpy(g_last_active_app_id, n->app_id, sizeof(g_last_active_app_id) - 1);
            strncpy(g_last_active_title, n->title, sizeof(g_last_active_title) - 1);
        }
    }
}

static void on_done(void *data, struct zcosmic_toplevel_handle_v1 *handle) {}

static void on_closed(void *data, struct zcosmic_toplevel_handle_v1 *handle) {
    struct ToplevelInfo **cur = &g_list;
    while (*cur) {
        if ((*cur)->handle == handle) {
            struct ToplevelInfo *tmp = *cur;
            *cur = (*cur)->next;
            if (g_last_active_handle == handle) {
                g_last_active_handle = NULL;
                g_last_active_app_id[0] = '\0';
                g_last_active_title[0] = '\0';
            }
            free(tmp);
            break;
        }
        cur = &(*cur)->next;
    }
    zcosmic_toplevel_handle_v1_destroy(handle);
}

static const struct zcosmic_toplevel_handle_v1_listener handle_listener = {
    .closed = on_closed,
    .done = on_done,
    .title = on_title,
    .app_id = on_app_id,
    .state = on_state,
};

static void on_info_toplevel(void *data, struct zcosmic_toplevel_info_v1 *info, struct zcosmic_toplevel_handle_v1 *toplevel) {
    get_or_create(toplevel);
    zcosmic_toplevel_handle_v1_add_listener(toplevel, &handle_listener, NULL);
}

static void on_info_finished(void *data, struct zcosmic_toplevel_info_v1 *info) {}
static void on_info_done(void *data, struct zcosmic_toplevel_info_v1 *info) {}

static const struct zcosmic_toplevel_info_v1_listener info_listener = {
    .toplevel = on_info_toplevel,
    .finished = on_info_finished,
    .done = on_info_done,
};

static void on_registry_global(void *data, struct wl_registry *registry, uint32_t name, const char *interface, uint32_t version) {
    if (strcmp(interface, "wl_seat") == 0) {
        g_seat = wl_registry_bind(registry, name, &wl_seat_interface, 1);
    } else if (strcmp(interface, "zcosmic_toplevel_info_v1") == 0) {
        g_info = wl_registry_bind(registry, name, &zcosmic_toplevel_info_v1_interface, 1);
        zcosmic_toplevel_info_v1_add_listener(g_info, &info_listener, NULL);
    } else if (strcmp(interface, "zcosmic_toplevel_manager_v1") == 0) {
        g_manager = wl_registry_bind(registry, name, &zcosmic_toplevel_manager_v1_interface, 1);
    }
}

static void on_registry_global_remove(void *data, struct wl_registry *registry, uint32_t name) {}

static const struct wl_registry_listener registry_listener = {
    .global = on_registry_global,
    .global_remove = on_registry_global_remove,
};

int cosmic_tracker_init(void) {
    if (g_display) return 1;
    g_display = wl_display_connect(NULL);
    if (!g_display) return 0;
    g_registry = wl_display_get_registry(g_display);
    wl_registry_add_listener(g_registry, &registry_listener, NULL);
    wl_display_roundtrip(g_display);
    wl_display_roundtrip(g_display);
    return (g_info && g_manager && g_seat) ? 1 : 0;
}

int cosmic_tracker_refresh(void) {
    if (!g_display) return 0;
    wl_display_roundtrip(g_display);
    return 1;
}

int cosmic_tracker_activate_target(void) {
    if (!g_manager || !g_seat || !g_last_active_handle) return 0;
    zcosmic_toplevel_manager_v1_activate(g_manager, g_last_active_handle, g_seat);
    wl_display_flush(g_display);
    return 1;
}

const char *cosmic_tracker_get_target_app_id(void) {
    return g_last_active_app_id;
}

const char *cosmic_tracker_get_target_title(void) {
    return g_last_active_title;
}

void cosmic_tracker_cleanup(void) {
    if (g_display) {
        wl_display_disconnect(g_display);
        g_display = NULL;
    }
}
