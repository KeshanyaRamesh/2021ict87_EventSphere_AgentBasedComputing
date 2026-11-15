
const API = "";

let token = localStorage.getItem("eventsphere_token") || "";
let currentUser = null;
let eventsCache = [];
let venuesCache = [];
let authMode = "login";
let toastTimer = null;

const $ = (id) => document.getElementById(id);

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function money(value) {
    return "LKR " + Number(value || 0).toLocaleString("en-LK", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function dateText(value) {
    if (!value) return "Not specified";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return escapeHTML(value);

    return date.toLocaleString();
}

function showToast(message, error = false) {
    const toast = $("toast");
    toast.textContent = message;
    toast.classList.toggle("error", error);
    toast.classList.add("show");

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, 3500);
}

async function api(path, options = {}) {
    const headers = {
        ...(options.headers || {})
    };

    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    if (
        options.body &&
        !(options.body instanceof FormData) &&
        typeof options.body !== "string"
    ) {
        headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(options.body);
    }

    const response = await fetch(API + path, {
        ...options,
        headers
    });

    const contentType = response.headers.get("content-type") || "";
    let result;

    if (contentType.includes("application/json")) {
        result = await response.json();
    } else {
        result = await response.text();
    }

    if (!response.ok) {
        let message = "Request failed";

        if (typeof result === "string") {
            message = result;
        } else if (typeof result.detail === "string") {
            message = result.detail;
        } else if (result.detail) {
            message = JSON.stringify(result.detail);
        } else if (result.message) {
            message = result.message;
        }

        if (response.status === 401) {
            logout(false);
        }

        throw new Error(message);
    }

    return result;
}

function setButtonLoading(button, loading, originalText) {
    if (!button) return;

    button.disabled = loading;
    button.textContent = loading ? "Please wait..." : originalText;
}

function openModal(id) {
    $(id).classList.remove("hidden");
}

function closeModal(id) {
    $(id).classList.add("hidden");
}

function showAuth(mode = "login") {
    authMode = mode;
    $("authTitle").textContent =
        mode === "login" ? "Welcome back" : "Create your account";

    $("authSubmit").textContent =
        mode === "login" ? "Login" : "Create account";

    $("nameField").classList.toggle(
        "hidden",
        mode === "login"
    );

    $("authForm").elements.full_name.required =
        mode === "register";

    $("authSwitch").innerHTML =
        mode === "login"
            ? 'New here? <button id="switchAuth" class="text-button" type="button">Create an account</button>'
            : 'Already registered? <button id="switchAuth" class="text-button" type="button">Login</button>';

    $("authMessage").textContent = "";
    openModal("authModal");

    $("switchAuth").addEventListener("click", () => {
        showAuth(authMode === "login" ? "register" : "login");
    });
}

function logout(showMessage = true) {
    token = "";
    currentUser = null;
    localStorage.removeItem("eventsphere_token");

    $("logoutBtn").classList.add("hidden");
    $("loginNav").classList.remove("hidden");
    $("registerNav").classList.remove("hidden");
    $("accountSection").classList.add("hidden");

    if (showMessage) {
        showToast("You have logged out.");
    }
}

function updateNavigation() {
    const loggedIn = Boolean(currentUser);

    $("loginNav").classList.toggle("hidden", loggedIn);
    $("registerNav").classList.toggle("hidden", loggedIn);
    $("logoutBtn").classList.toggle("hidden", !loggedIn);
}

function statusBadge(status) {
    const value = String(status || "unknown").toLowerCase();

    return `<span class="status ${escapeHTML(value)}">${escapeHTML(value)}</span>`;
}

function emptyState(message) {
    return `<div class="empty-state">${escapeHTML(message)}</div>`;
}


// -------------------------------------------------
// AUTHENTICATION
// -------------------------------------------------

async function handleAuthSubmit(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const button = $("authSubmit");
    const originalText = authMode === "login"
        ? "Login"
        : "Create account";

    setButtonLoading(button, true, originalText);
    $("authMessage").textContent = "";

    try {
        const formData = new FormData(form);
        const email = formData.get("email");
        const password = formData.get("password");

        if (authMode === "register") {
            await api("/api/auth/register", {
                method: "POST",
                body: {
                    full_name: formData.get("full_name"),
                    email,
                    password
                }
            });

            showToast("Account created. Please log in.");
            showAuth("login");
            $("authForm").elements.email.value = email;
            return;
        }

        const result = await api("/api/auth/login-json", {
            method: "POST",
            body: { email, password }
        });

        token = result.access_token;
        localStorage.setItem("eventsphere_token", token);

        await loadProfile();
        closeModal("authModal");
        showToast("Login successful.");
        $("accountSection").scrollIntoView({
            behavior: "smooth"
        });

    } catch (error) {
        $("authMessage").textContent = error.message;
        $("authMessage").style.color = "#ff7185";
    } finally {
        setButtonLoading(button, false, originalText);
    }
}

async function loadProfile() {
    if (!token) return;

    try {
        currentUser = await api("/api/auth/me");
        updateNavigation();

        $("accountSection").classList.remove("hidden");
        $("welcomeText").textContent =
            `Welcome, ${currentUser.name}. Signed in as ${currentUser.role}.`;

        $("accountTitle").textContent =
            currentUser.role === "admin"
                ? "Administrator dashboard"
                : currentUser.role === "staff"
                    ? "Gate staff dashboard"
                    : "Attendee dashboard";

        $("attendeePanel").classList.toggle(
            "hidden",
            currentUser.role !== "attendee"
        );

        $("adminPanel").classList.toggle(
            "hidden",
            currentUser.role !== "admin"
        );

        $("staffPanel").classList.toggle(
            "hidden",
            currentUser.role !== "staff" && currentUser.role !== "admin"
        );

        if (currentUser.role === "attendee") {
            await loadBookingHistory();
            await loadHireHistory();
            await loadNotifications();
        }

        if (currentUser.role === "admin") {
            await loadAdminDashboard();
            await loadAdminEvents();
            await loadAdminHireRequests();
            await loadAgentLogs();
            await loadVenues();
        }

        if (currentUser.role === "staff" || currentUser.role === "admin") {
            prepareScanner();
        }

    } catch (error) {
        console.error("Profile loading error:", error);
        logout(false);
        showToast("Your session has expired. Please log in again.", true);
    }
}


// -------------------------------------------------
// PUBLIC EVENTS
// -------------------------------------------------

async function loadEvents() {
    const keyword = $("searchInput").value.trim();
    const category = $("categoryFilter").value;

    const params = new URLSearchParams();

    if (keyword) params.set("keyword", keyword);
    if (category) params.set("category", category);

    $("eventsGrid").innerHTML =
        '<p class="muted">Loading events...</p>';

    try {
        eventsCache = await api(
            `/api/events?${params.toString()}`
        );

        renderEvents(eventsCache);
        updateEventStats(eventsCache);

    } catch (error) {
        $("eventsGrid").innerHTML = emptyState(error.message);
    }
}

function updateEventStats(events) {
    $("heroEventCount").textContent = events.length;
}

function renderEvents(events) {
    const grid = $("eventsGrid");

    if (!events.length) {
        grid.innerHTML = emptyState(
            "No published events found. Please check again later."
        );
        return;
    }

    const categories = [
        ...new Set(events.map(event => event.category).filter(Boolean))
    ];

    const select = $("categoryFilter");
    const current = select.value;

    select.innerHTML =
        '<option value="">All categories</option>' +
        categories.map(category =>
            `<option value="${escapeHTML(category)}">${escapeHTML(category)}</option>`
        ).join("");

    if (categories.includes(current)) {
        select.value = current;
    }

    grid.innerHTML = events.map(event => {
        const available = event.tickets.reduce(
            (sum, ticket) => sum + Number(ticket.available || 0),
            0
        );

        const lowestPrice = event.tickets.length
            ? Math.min(...event.tickets.map(ticket => Number(ticket.price)))
            : 0;

        return `
            <article class="event-card">
                <div class="event-cover">✦</div>
                <div class="event-body">
                    <span class="event-category">${escapeHTML(event.category)}</span>
                    <h3>${escapeHTML(event.title)}</h3>
                    <p>📍 ${escapeHTML(event.venue_name || "University venue")}</p>
                    <p>📅 ${dateText(event.start_time)}</p>
                    <p>${escapeHTML((event.description || "Discover this university event.").slice(0, 120))}</p>
                    <div class="event-footer">
                        <strong>${money(lowestPrice)} onwards</strong>
                        <button class="button button-primary small-button" data-event-details="${event.id}">
                            View details
                        </button>
                    </div>
                    <p>${available} tickets available</p>
                </div>
            </article>
        `;
    }).join("");
}

function showEventDetails(eventId) {
    const event = eventsCache.find(
        item => Number(item.id) === Number(eventId)
    );

    if (!event) {
        showToast("Event details are unavailable.", true);
        return;
    }

    const ticketRows = event.tickets.map(ticket => `
        <div class="list-item">
            <strong>${escapeHTML(ticket.name)}</strong>
            <p>${money(ticket.price)} · ${ticket.available} available</p>
            ${
                ticket.available > 0
                    ? `
                    <label>
                        Quantity
                        <input
                            id="quantity-${ticket.id}"
                            type="number"
                            min="1"
                            max="${Math.min(6, ticket.available)}"
                            value="1"
                        >
                    </label>
                    <button
                        class="button button-primary small-button"
                        data-book-ticket="${ticket.id}"
                        data-event-id="${event.id}"
                    >Book tickets</button>
                    `
                    : `
                    <button
                        class="button button-outline small-button"
                        data-waitlist="${ticket.id}"
                        data-event-id="${event.id}"
                    >Join waitlist</button>
                    `
            }
        </div>
    `).join("");

    $("eventDetails").innerHTML = `
        <span class="eyebrow">${escapeHTML(event.category)}</span>
        <h2>${escapeHTML(event.title)}</h2>
        <p class="muted">📍 ${escapeHTML(event.venue_name || "University venue")}</p>
        <p class="muted">📅 ${dateText(event.start_time)}</p>
        <p class="muted">End: ${dateText(event.end_time)}</p>
        <p style="margin:18px 0">${escapeHTML(event.description || "No description provided.")}</p>
        <h3>Ticket categories</h3>
        ${ticketRows || emptyState("No ticket categories available.")}
        <p id="eventActionMessage" class="muted"></p>
    `;

    openModal("eventModal");
}

async function bookTicket(eventId, categoryId) {
    if (!currentUser) {
        closeModal("eventModal");
        showAuth("login");
        showToast("Please log in to book tickets.");
        return;
    }

    if (currentUser.role !== "attendee") {
        showToast("Only attendee accounts can book tickets.", true);
        return;
    }

    const quantityInput = $(`quantity-${categoryId}`);
    const quantity = Number(quantityInput?.value || 1);

    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 6) {
        showToast("Choose a quantity between 1 and 6.", true);
        return;
    }

    try {
        const result = await api("/api/bookings", {
            method: "POST",
            body: {
                event_id: Number(eventId),
                category_id: Number(categoryId),
                quantity
            }
        });

        const qrImages = result.qr_codes || [];
        const ticketCodes = result.tickets || [];

        $("eventActionMessage").innerHTML = `
            <p style="color:#40d6a0">Booking confirmed. Reference: ${escapeHTML(result.booking.payment_reference || result.booking.booking_id || "")}</p>
            <div class="qr-list">
                ${qrImages.map((image, index) => `
                    <div class="qr-ticket">
                        <img src="data:image/png;base64,${image}" alt="Ticket QR code">
                        <small>Ticket ${index + 1}</small>
                        <code>${escapeHTML(ticketCodes[index] || "")}</code>
                    </div>
                `).join("")}
            </div>
            <p class="muted">Save your QR ticket and show it at the event entrance.</p>
        `;

        showToast("Your ticket booking was successful.");
        await loadEvents();
        await loadBookingHistory();

    } catch (error) {
        showToast(error.message, true);
    }
}

async function joinWaitlist(eventId, categoryId) {
    if (!currentUser) {
        closeModal("eventModal");
        showAuth("login");
        return;
    }

    if (currentUser.role !== "attendee") {
        showToast("Only attendees can join a waitlist.", true);
        return;
    }

    try {
        const result = await api("/api/waitlist", {
            method: "POST",
            body: {
                event_id: Number(eventId),
                category_id: Number(categoryId)
            }
        });

        showToast(result.message || "You joined the waitlist.");
    } catch (error) {
        showToast(error.message, true);
    }
}


// -------------------------------------------------
// VENUES
// -------------------------------------------------

async function loadVenues() {
    try {
        venuesCache = await api("/api/venues");

        $("heroVenueCount").textContent = venuesCache.length;

        const options = venuesCache.map(venue => `
            <option value="${venue.id}">
                ${escapeHTML(venue.name)} — ${escapeHTML(venue.location)}
            </option>
        `).join("");

        $("hireVenue").innerHTML =
            '<option value="">Choose a venue</option>' + options;

        $("eventVenue").innerHTML =
            '<option value="">Choose a venue</option>' + options;

    } catch (error) {
        console.error("Venue loading error:", error);
    }
}


// -------------------------------------------------
// ATTENDEE BOOKINGS
// -------------------------------------------------

async function loadBookingHistory() {
    try {
        const bookings = await api("/api/bookings/history");

        if (!bookings.length) {
            $("bookingHistory").innerHTML =
                emptyState("You have not booked any tickets yet.");
            return;
        }

        $("bookingHistory").innerHTML = bookings.map(booking => `
            <div class="list-item">
                <strong>${escapeHTML(booking.event_title || `Event #${booking.event_id}`)}</strong>
                <p>Booking #${booking.booking_id} · ${booking.quantity} ticket(s)</p>
                <p>Amount: ${money(booking.total_amount)}</p>
                <p>Payment reference: ${escapeHTML(booking.payment_reference || "N/A")}</p>
                <p>Status: ${statusBadge(booking.status)}</p>
                ${
                    booking.status === "confirmed"
                        ? `<button class="button button-outline small-button" data-cancel-booking="${booking.booking_id}">Cancel booking</button>`
                        : ""
                }
                <div class="qr-list">
                    ${(booking.tickets || []).map(ticket => `
                        <div class="qr-ticket">
                            <strong>Ticket #${ticket.id}</strong>
                            <p>${statusBadge(ticket.status)}</p>
                            <code>${escapeHTML(ticket.qr_code)}</code>
                        </div>
                    `).join("")}
                </div>
            </div>
        `).join("");

    } catch (error) {
        $("bookingHistory").innerHTML = emptyState(error.message);
    }
}

async function cancelBooking(bookingId) {
    if (!confirm("Are you sure you want to cancel this booking? The applicable refund policy will be applied.")) {
        return;
    }

    try {
        const result = await api(`/api/bookings/${bookingId}/cancel`, {
            method: "POST"
        });

        showToast(
            `Booking cancelled. Refund: ${money(result.refund_amount)}`
        );

        await loadBookingHistory();
        await loadEvents();

    } catch (error) {
        showToast(error.message, true);
    }
}


// -------------------------------------------------
// PRIVATE VENUE HIRE
// -------------------------------------------------

async function submitHireRequest(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));

    data.venue_id = Number(data.venue_id);
    data.guest_count = Number(data.guest_count);

    if (!data.venue_id) {
        showToast("Please select a venue.", true);
        return;
    }

    try {
        const result = await api("/api/venue-hire", {
            method: "POST",
            body: data
        });

        showToast(result.message || "Hire request submitted.");
        form.reset();

        await loadHireHistory();

    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadHireHistory() {
    try {
        const requests = await api("/api/venue-hire/my-requests");

        if (!requests.length) {
            $("hireHistory").innerHTML =
                emptyState("No private venue hire requests yet.");
            return;
        }

        $("hireHistory").innerHTML = `
            <h4 style="margin:20px 0 10px">My hire requests</h4>
            ${requests.map(request => `
                <div class="list-item">
                    <strong>Request #${request.request_id}</strong>
                    <p>Venue ID: ${request.venue_id}</p>
                    <p>${dateText(request.start_time)} – ${dateText(request.end_time)}</p>
                    <p>Purpose: ${escapeHTML(request.purpose)}</p>
                    <p>Guests: ${request.guest_count}</p>
                    <p>Quoted price: ${money(request.quoted_price)}</p>
                    <p>Status: ${statusBadge(request.status)}</p>
                </div>
            `).join("")}
        `;

    } catch (error) {
        $("hireHistory").innerHTML = emptyState(error.message);
    }
}

async function loadNotifications() {
    try {
        const notifications = await api("/api/notifications");

        if (!notifications.length) {
            $("notifications").innerHTML =
                emptyState("No notifications yet.");
            return;
        }

        $("notifications").innerHTML = notifications.map(item => `
            <div class="message-item">
                <strong>${escapeHTML(item.type || "Notification")}</strong>
                <p>${escapeHTML(item.message || JSON.stringify(item))}</p>
            </div>
        `).join("");

    } catch (error) {
        $("notifications").innerHTML = emptyState(error.message);
    }
}


// -------------------------------------------------
// ADMIN DASHBOARD
// -------------------------------------------------

async function loadAdminDashboard() {
    try {
        const data = await api("/api/admin/dashboard");

        $("adminStats").innerHTML = `
            <div class="stat-card">
                <span>Published events</span>
                <strong>${data.total_published_events}</strong>
            </div>
            <div class="stat-card">
                <span>Total venues</span>
                <strong>${data.total_venues}</strong>
            </div>
            <div class="stat-card">
                <span>Confirmed bookings</span>
                <strong>${data.confirmed_bookings}</strong>
            </div>
            <div class="stat-card">
                <span>Tickets sold</span>
                <strong>${data.tickets_sold}</strong>
            </div>
            <div class="stat-card">
                <span>Simulated revenue</span>
                <strong>${money(data.simulated_revenue)}</strong>
            </div>
            <div class="stat-card">
                <span>Check-ins</span>
                <strong>${data.total_checkins}</strong>
            </div>
        `;

        if (data.events?.length) {
            $("adminStats").insertAdjacentHTML("afterend", `
                <div class="panel">
                    <h3>Event capacity overview</h3>
                    <div class="data-table-wrap">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Event</th>
                                    <th>Status</th>
                                    <th>Capacity</th>
                                    <th>Sold</th>
                                    <th>Available</th>
                                    <th>Check-ins</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.events.map(item => `
                                    <tr>
                                        <td>${escapeHTML(item.title)}</td>
                                        <td>${statusBadge(item.status)}</td>
                                        <td>${item.capacity}</td>
                                        <td>${item.tickets_sold}</td>
                                        <td>${item.tickets_available}</td>
                                        <td>${item.checked_in}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </div>
            `);
        }

    } catch (error) {
        $("adminStats").innerHTML = emptyState(error.message);
    }
}

async function submitVenue(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const formData = new FormData(form);

    const data = {
        name: formData.get("name"),
        location: formData.get("location"),
        capacity: Number(formData.get("capacity")),
        hourly_rate: Number(formData.get("hourly_rate")),
        image: formData.get("image") || null,
        description: formData.get("description") || null,
        available_for_hire: formData.get("available_for_hire") === "on"
    };

    try {
        await api("/api/admin/venues", {
            method: "POST",
            body: data
        });

        showToast("Venue created successfully.");
        form.reset();

        await loadVenues();
        await loadAdminDashboard();

    } catch (error) {
        showToast(error.message, true);
    }
}

async function submitEvent(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const formData = new FormData(form);

    const data = {
        title: formData.get("title"),
        category: formData.get("category"),
        venue_id: Number(formData.get("venue_id")),
        start_time: formData.get("start_time"),
        end_time: formData.get("end_time"),
        description: formData.get("description") || "",
        ticket_categories: [
            {
                name: formData.get("ticket_name"),
                price: Number(formData.get("ticket_price")),
                quantity: Number(formData.get("ticket_quantity"))
            }
        ]
    };

    try {
        await api("/api/admin/events", {
            method: "POST",
            body: data
        });

        showToast("Event draft created successfully.");
        form.reset();

        await loadAdminEvents();
        await loadAdminDashboard();

    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadAdminEvents() {
    try {
        const events = await api("/api/admin/events");

        if (!events.length) {
            $("adminEvents").innerHTML =
                emptyState("No events have been created.");
            return;
        }

        $("adminEvents").innerHTML = `
            <div class="data-table-wrap">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Event</th>
                            <th>Venue</th>
                            <th>Status</th>
                            <th>Sold</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${events.map(event => `
                            <tr>
                                <td>${event.id}</td>
                                <td>${escapeHTML(event.title)}</td>
                                <td>${escapeHTML(event.venue_name || event.venue_id)}</td>
                                <td>${statusBadge(event.status)}</td>
                                <td>${event.tickets_sold}/${event.total_capacity}</td>
                                <td>
                                    ${
                                        event.status === "draft"
                                            ? `<button class="button button-primary small-button" data-publish-event="${event.id}">Publish</button>`
                                            : ""
                                    }
                                    ${
                                        event.status !== "cancelled"
                                            ? `<button class="button button-outline small-button" data-cancel-event="${event.id}">Cancel</button>`
                                            : ""
                                    }
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;

    } catch (error) {
        $("adminEvents").innerHTML = emptyState(error.message);
    }
}

async function publishEvent(eventId) {
    try {
        const result = await api(
            `/api/admin/events/${eventId}/publish`,
            { method: "POST" }
        );

        showToast(result.message || "Event published.");
        await loadAdminEvents();
        await loadEvents();
        await loadAdminDashboard();

    } catch (error) {
        showToast(error.message, true);
    }
}

async function cancelEvent(eventId) {
    if (!confirm("Cancel this event? Confirmed bookings will be cancelled.")) {
        return;
    }

    try {
        const result = await api(
            `/api/admin/events/${eventId}/cancel`,
            { method: "POST" }
        );

        showToast(result.message || "Event cancelled.");
        await loadAdminEvents();
        await loadEvents();
        await loadAdminDashboard();

    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadAdminHireRequests() {
    try {
        const requests = await api("/api/admin/venue-hire-requests");

        if (!requests.length) {
            $("adminHireRequests").innerHTML =
                emptyState("No private hire requests.");
            return;
        }

        $("adminHireRequests").innerHTML = requests.map(request => `
            <div class="list-item">
                <strong>Request #${request.request_id}</strong>
                <p>User ID: ${request.user_id} · Venue ID: ${request.venue_id}</p>
                <p>${dateText(request.start_time)} – ${dateText(request.end_time)}</p>
                <p>Purpose: ${escapeHTML(request.purpose)}</p>
                <p>Guests: ${request.guest_count} · Price: ${money(request.quoted_price)}</p>
                <p>Status: ${statusBadge(request.status)}</p>
                ${
                    ["pending", "proposed"].includes(request.status)
                        ? `
                        <button class="button button-primary small-button" data-approve-hire="${request.request_id}">Approve</button>
                        <button class="button button-outline small-button" data-reject-hire="${request.request_id}">Reject</button>
                        `
                        : ""
                }
            </div>
        `).join("");

    } catch (error) {
        $("adminHireRequests").innerHTML = emptyState(error.message);
    }
}

async function approveHire(requestId) {
    try {
        const result = await api(
            `/api/admin/venue-hire-requests/${requestId}/approve`,
            { method: "POST" }
        );

        showToast(result.message || "Hire request approved.");
        await loadAdminHireRequests();

    } catch (error) {
        showToast(error.message, true);
    }
}

async function rejectHire(requestId) {
    if (!confirm("Reject this venue hire request?")) return;

    try {
        const result = await api(
            `/api/admin/venue-hire-requests/${requestId}/reject`,
            { method: "POST" }
        );

        showToast(result.message || "Hire request rejected.");
        await loadAdminHireRequests();

    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadAgentLogs() {
    try {
        const messages = await api("/api/admin/agent-messages");

        if (!messages.length) {
            $("agentLogs").innerHTML =
                emptyState("No agent messages recorded yet.");
            return;
        }

        $("agentLogs").innerHTML = `
            <div class="data-table-wrap">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Sender</th>
                            <th>Receiver</th>
                            <th>Performative</th>
                            <th>Content</th>
                            <th>Conversation</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${messages.map(message => `
                            <tr>
                                <td>${dateText(message.created_at)}</td>
                                <td>${escapeHTML(message.sender)}</td>
                                <td>${escapeHTML(message.receiver)}</td>
                                <td>${statusBadge(message.performative)}</td>
                                <td>${escapeHTML(message.content)}</td>
                                <td>${escapeHTML(message.conversation_id)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;

    } catch (error) {
        $("agentLogs").innerHTML = emptyState(error.message);
    }
}


// -------------------------------------------------
// STAFF TICKET SCANNER
// -------------------------------------------------

function prepareScanner() {
    const panel = $("staffPanel");
    if (!panel || $("cameraScannerArea")) return;

    const scannerArea = document.createElement("div");
    scannerArea.id = "cameraScannerArea";
    scannerArea.innerHTML = `
        <div style="margin-top:20px">
            <button type="button" id="startCameraScan" class="button button-outline">
                Start camera QR scanner
            </button>
            <button type="button" id="stopCameraScan" class="button button-outline hidden">
                Stop camera
            </button>
            <div id="qr-reader" style="max-width:420px;margin-top:15px"></div>
            <p class="muted" style="margin-top:8px">
                Camera scanning requires HTTPS or localhost and browser camera permission.
                Manual ticket-code entry is also available above.
            </p>
        </div>
    `;

    $("scanForm").insertAdjacentElement("afterend", scannerArea);

    $("startCameraScan").addEventListener("click", startCameraScanner);
    $("stopCameraScan").addEventListener("click", stopCameraScanner);
}

let qrScanner = null;

async function startCameraScanner() {
    try {
        if (!window.Html5Qrcode) {
            await new Promise((resolve, reject) => {
                const script = document.createElement("script");
                script.src = "https://unpkg.com/html5-qrcode";
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
        }

        qrScanner = new Html5Qrcode("qr-reader");

        await qrScanner.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: { width: 230, height: 230 } },
            async decodedText => {
                $("scanForm").elements.code.value = decodedText;
                await stopCameraScanner();
                showToast("QR code captured. Select the event ID and submit.");
            },
            () => {}
        );

        $("startCameraScan").classList.add("hidden");
        $("stopCameraScan").classList.remove("hidden");

    } catch (error) {
        showToast(
            "Camera could not start. Check browser permission or use manual scanning.",
            true
        );
        console.error(error);
    }
}

async function stopCameraScanner() {
    if (qrScanner) {
        try {
            await qrScanner.stop();
            await qrScanner.clear();
        } catch (error) {
            console.warn("Scanner stop:", error);
        }

        qrScanner = null;
    }

    $("startCameraScan")?.classList.remove("hidden");
    $("stopCameraScan")?.classList.add("hidden");
}

async function submitScan(event) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);

    try {
        const result = await api("/api/staff/scan", {
            method: "POST",
            body: {
                code: formData.get("code").trim(),
                event_id: Number(formData.get("event_id"))
            }
        });

        $("scanResult").innerHTML = `
            <div class="list-item">
                <strong style="color:#40d6a0">Ticket accepted</strong>
                <p>${escapeHTML(JSON.stringify(result))}</p>
            </div>
        `;

        showToast("Ticket successfully admitted.");

    } catch (error) {
        $("scanResult").innerHTML = `
            <div class="list-item">
                <strong style="color:#ff7185">Ticket rejected</strong>
                <p>${escapeHTML(error.message)}</p>
            </div>
        `;

        showToast(error.message, true);
    }
}


// -------------------------------------------------
// EVENT LISTENERS
// -------------------------------------------------

$("loginNav").addEventListener("click", () => showAuth("login"));
$("registerNav").addEventListener("click", () => showAuth("register"));
$("heroLogin").addEventListener("click", () => showAuth("login"));
$("logoutBtn").addEventListener("click", () => logout());

$("closeModal").addEventListener("click", () => closeModal("authModal"));
$("closeEventModal").addEventListener("click", () => closeModal("eventModal"));

$("authModal").addEventListener("click", event => {
    if (event.target === $("authModal")) closeModal("authModal");
});

$("eventModal").addEventListener("click", event => {
    if (event.target === $("eventModal")) closeModal("eventModal");
});

$("authForm").addEventListener("submit", handleAuthSubmit);
$("searchBtn").addEventListener("click", loadEvents);

$("searchInput").addEventListener("keydown", event => {
    if (event.key === "Enter") loadEvents();
});

$("categoryFilter").addEventListener("change", loadEvents);
$("hireForm").addEventListener("submit", submitHireRequest);
$("venueForm").addEventListener("submit", submitVenue);
$("eventForm").addEventListener("submit", submitEvent);
$("scanForm").addEventListener("submit", submitScan);

document.addEventListener("click", async event => {
    const target = event.target.closest("button");
    if (!target) return;

    if (target.dataset.eventDetails) {
        showEventDetails(target.dataset.eventDetails);
    }

    if (target.dataset.bookTicket) {
        await bookTicket(
            target.dataset.eventId,
            target.dataset.bookTicket
        );
    }

    if (target.dataset.waitlist) {
        await joinWaitlist(
            target.dataset.eventId,
            target.dataset.waitlist
        );
    }

    if (target.dataset.cancelBooking) {
        await cancelBooking(target.dataset.cancelBooking);
    }

    if (target.dataset.publishEvent) {
        await publishEvent(target.dataset.publishEvent);
    }

    if (target.dataset.cancelEvent) {
        await cancelEvent(target.dataset.cancelEvent);
    }

    if (target.dataset.approveHire) {
        await approveHire(target.dataset.approveHire);
    }

    if (target.dataset.rejectHire) {
        await rejectHire(target.dataset.rejectHire);
    }
});


// -------------------------------------------------
// APPLICATION STARTUP
// -------------------------------------------------

async function initialiseApp() {
    await loadEvents();
    await loadVenues();

    if (token) {
        await loadProfile();
    }
}

initialiseApp();
