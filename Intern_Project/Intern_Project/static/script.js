const API_URL = window.location.origin;

const DEFAULT_CATEGORIES = ["Food🍕", "Transport🚂", "Bills💸", "Entertainment🤡", "Shopping🛍️", "Therapy 🩺", "Others"];

const messages = [
    "💸 Counting your regrets… I mean, transactions… 💸",
    "🏦 Asking your bank if it’s okay to proceed… 📞",
    "🎢 Analyzing your financial rollercoaster… 📊",
    "🛍️ Rethinking that last online shopping spree… 🤔",
    "🛒 Compiling all your 'just one more' purchases… 💳",
    "💳 Checking if your card is still breathing… 🚑",
    "🍕 Calculating how much of your salary went to food… 😋",
    "🎰 Spinning the wheel of 'Do I have enough money?' 🤞",
    "🏖️ Searching for your retirement fund… Found: 404 🔎",
    "🏃‍♂️ Watching your money run faster than you… 💨",
    "📅 Estimating how long until payday saves you… ⏳",
    "🔎 Looking for savings… Please wait… 🧐",
    "💰 Your money was here… and now it’s gone! 💨",
    "🚀 Sending a rescue mission for your budget… 🆘",
    "🤷‍♂️ Trying to explain your expenses to your future self… 😬"
];

function displayRandomMessage() {
    const messageContainer = document.getElementById("message");
    const randomMessage = messages[Math.floor(Math.random() * messages.length)];
    messageContainer.textContent = randomMessage;
    messageContainer.style.textAlign = "center";
}

// Function to strip emojis from a string
function stripEmojis(text) {
    return text.replace(/[\u{1F600}-\u{1F64F}]/gu, '')
               .replace(/[\u{1F300}-\u{1F5FF}]/gu, '')
               .replace(/[\u{1F680}-\u{1F6FF}]/gu, '')
               .replace(/[\u{1F700}-\u{1F77F}]/gu, '')
               .replace(/[\u{1F780}-\u{1F7FF}]/gu, '')
               .replace(/[\u{1F800}-\u{1F8FF}]/gu, '')
               .replace(/[\u{1F900}-\u{1F9FF}]/gu, '')
               .replace(/[\u{1FA00}-\u{1FA6F}]/gu, '')
               .replace(/[\u{1FA70}-\u{1FAFF}]/gu, '')
               .replace(/[\u{2600}-\u{26FF}]/gu, '')
               .replace(/[\u{2700}-\u{27BF}]/gu, '');
}

// Fetch categories and populate dropdown
async function fetchCategories() {
    let select = document.getElementById("category");
    select.innerHTML = '<option value="">Select</option>';
    DEFAULT_CATEGORIES.forEach(cat => {
        let option = document.createElement("option");
        option.value = cat; // Keep emojis here for display
        option.textContent = cat;
        select.appendChild(option);
    });
}

// Show/hide custom category input
document.getElementById("category").addEventListener("change", function() {
    const customCategoryLabel = document.getElementById("custom-category-label");
    const customCategoryInput = document.getElementById("custom-category");
    if (this.value === "Others") {
        customCategoryLabel.style.display = "block";
        customCategoryInput.required = true;
    } else {
        customCategoryLabel.style.display = "none";
        customCategoryInput.required = false;
    }
});

// Update file upload label with file name
document.getElementById("file-upload").addEventListener("change", function() {
    const fileName = this.files[0] ? this.files[0].name : "Upload File";
    document.getElementById("file-upload-label").textContent = fileName;
});

// Fetch and display expenses
async function fetchExpenses(fromDate = "", toDate = "") {
    let url = `${API_URL}/get_expenses`;
    if (fromDate && toDate) {
        url += `?from_date=${fromDate}&to_date=${toDate}`;
    }
    const response = await fetch(url);
    const expenses = await response.json();
    const tableBody = document.getElementById("expense-table-body");
    tableBody.innerHTML = "";

    expenses.forEach(exp => {
        const row = document.createElement("tr");
        row.setAttribute("data-id", exp.id);
        row.innerHTML = `
            <td>${exp.username}</td>
            <td>${exp.name}</td>
            <td>${exp.date}</td>
            <td>${exp.category}</td>
            <td>${exp.description || ""}</td>
            <td>₹${exp.amount}</td>
            <td>
                <button class="edit-btn edit" onclick="editExpense(${exp.id})">✏️</button>
                <button class="delete-btn delete" onclick="deleteExpense(${exp.id})">❌</button>
            </td>
            <td>
                ${exp.image_url ? getFileLink(exp.image_url, exp.file_type) : "No file"}
            </td>
        `;
        tableBody.appendChild(row);
    });
    updateStats(fromDate, toDate);
}

function getFileLink(url, fileType) {
    const imageTypes = ["image/jpeg", "image/png"];
    if (imageTypes.includes(fileType)) {
        return `<img src="${url}" class="thumbnail" onclick="showImagePopup('${url}')" />`;
    } else if (fileType === "application/pdf") {
        return `<a href="${url}" target="_blank">👀📄</a>`;
    } else if (fileType === "application/msword" || fileType === "application/vnd.openxmlformats-officedocument.wordprocessingml.document") {
        return `<a href="${url}" target="_blank">📥📄</a>`;
    } else {
        return `<a href="${url}" target="_blank">View File</a>`;
    }
}

function openPdfInNewTab(url) {
    fetch(url)
        .then(response => response.blob())
        .then(blob => {
            const blobUrl = URL.createObjectURL(blob);
            window.open(blobUrl, '_blank');
        })
        .catch(error => console.error('Error opening PDF:', error));
}

// Show image in a popup
function showImagePopup(imageUrl) {
    const popup = document.createElement("div");
    popup.classList.add("image-popup");
    popup.innerHTML = `
        <div class="popup-content">
            <span class="close-btn" onclick="closeImagePopup()">&times;</span>
            <img src="${imageUrl}" />
        </div>
    `;
    document.body.appendChild(popup);
}

// Close image popup
function closeImagePopup() {
    const popup = document.querySelector(".image-popup");
    if (popup) {
        popup.remove();
    }
}

// Add new expense
document.getElementById("expense-form").addEventListener("submit", async function(event) {
    event.preventDefault();
    const formData = new FormData(event.target);

    // Handle custom category
    const categorySelect = document.getElementById("category");
    if (categorySelect.value === "Others") {
        const customCategory = document.getElementById("custom-category").value;
        formData.set("category", stripEmojis(customCategory));
    } else {
        formData.set("category", stripEmojis(categorySelect.value));
    }

    const expenseId = document.getElementById("expense-id").value;
    let url = `${API_URL}/add_expense`;
    let method = "POST";
    if (expenseId) {
        url = `${API_URL}/edit_expense/${expenseId}`;
        method = "PUT";
    }
    await fetch(url, {
        method: method,
        body: formData
    });
    fetchExpenses();
    fetchStats();
    event.target.reset();
    document.getElementById("custom-category-label").style.display = "none";
    document.getElementById("expense-id").value = "";
    document.getElementById("file-upload-label").textContent = "Upload File";
});

// Edit expense
async function fetchExpenseDetails(id) {
    const response = await fetch(`${API_URL}/get_expense/${id}`);
    if (response.status === 404) {
        alert("Expense not found");
        return;
    }
    const expense = await response.json();
    document.getElementById("expense-id").value = expense.id;
    document.getElementById("name").value = expense.name;
    document.getElementById("category").value = expense.category;
    document.getElementById("category-desc").value = expense.category_desc;
    document.getElementById("date").value = expense.date;
    document.getElementById("amount").value = expense.amount;
    document.getElementById("description").value = expense.description;
    document.getElementById("file-upload").value = "";
    if (expense.category === "Others" || !DEFAULT_CATEGORIES.includes(expense.category)) {
        document.getElementById("custom-category-label").style.display = "block";
        document.getElementById("custom-category").value = expense.category;
        document.getElementById("category").value = "Others";
    } else {
        document.getElementById("custom-category-label").style.display = "none";
    }
}

async function editExpense(id) {
    await fetchExpenseDetails(id);
    document.getElementById("expense-form").scrollIntoView({ behavior: "smooth" });
}

// Delete expense
async function deleteExpense(id) {
    if (!confirm("😃Sure you want to Delete?")) return;
    await fetch(`${API_URL}/delete_expense/${id}`, { method: "DELETE" });
    fetchExpenses();
    setTimeout(fetchStats, 500);
}

// Filter expenses by date
document.getElementById("filter-btn").addEventListener("click", function() {
    const fromDate = document.getElementById("from-date").value;
    const toDate = document.getElementById("to-date").value;
    if (!fromDate || !toDate) {
        const alertBox = document.createElement("div");
        alertBox.textContent = "😯Please fill out both date fields😅 ";
        alertBox.style.position = "fixed";
        alertBox.style.top = "5px";
        alertBox.style.left = "50%";
        alertBox.style.transform = "translateX(-50%)";
        alertBox.style.backgroundColor = "#f44336";
        alertBox.style.color = "#fff";
        alertBox.style.padding = "20px";
        alertBox.style.borderRadius = "20px";
        alertBox.style.boxShadow = "3px 3px 10px rgba(0, 0, 0, 0.1)";
        document.body.appendChild(alertBox);
        setTimeout(() => { document.body.removeChild(alertBox); }, 2000);
        return;
    }
    fetchExpenses(fromDate, toDate);
});

// Refresh expense list
document.getElementById("refresh-btn").addEventListener("click", function() {
    document.getElementById("from-date").value = "";
    document.getElementById("to-date").value = "";
    fetchExpenses();
    fetchStats();
});

// Fetch and update stats
async function fetchStats() {
    const response = await fetch(`${API_URL}/get_stats`);
    const stats = await response.json();
    document.getElementById("total-spent-value").textContent = stats.total_spent.toFixed(2);
    document.getElementById("expense-count-value").textContent = stats.expense_count;
    document.getElementById("last-7days-spent-value").textContent = stats.last_7days_spent.toFixed(2);
    document.getElementById("highest-category-value").textContent = stats.highest_category;
    document.getElementById("highest-amount-value").textContent = stats.highest_amount.toFixed(2);
}

// Update stats based on filtered expenses
async function updateStats(fromDate, toDate) {
    let url = `${API_URL}/get_stats`;
    if (fromDate && toDate) {
        url += `?from_date=${fromDate}&to_date=${toDate}`;
    }
    const response = await fetch(url);
    const stats = await response.json();
    document.getElementById("total-spent-value").textContent = stats.total_spent.toFixed(2);
    document.getElementById("expense-count-value").textContent = stats.expense_count;
    document.getElementById("last-7days-spent-value").textContent = stats.last_7days_spent.toFixed(2);
    document.getElementById("highest-category-value").textContent = stats.highest_category;
    document.getElementById("highest-amount-value").textContent = stats.highest_amount.toFixed(2);
}

// Populate year select dropdown
function populateYearSelect() {
    const yearSelect = document.getElementById("year-select");
    const currentYear = new Date().getFullYear();
    for (let i = currentYear; i <= currentYear + 10; i++) {
        const option = document.createElement("option");
        option.value = i;
        option.textContent = i;
        yearSelect.appendChild(option);
    }
}

// ----- Month & Year Section: Set Period ----- //
document.getElementById("month-year-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    const year = document.getElementById("year-select").value;
    const month = document.getElementById("month-select").value;
    const prompt = document.getElementById("month-year-prompt");
    if (!year || !month) {
        showTemporaryAlert('⚠️ Please select both year and month!', 'error');
        return;
    }
    try {
        const response = await fetch(`${API_URL}/set_period`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ year: parseInt(year), month: parseInt(month) })
        });
        const result = await response.json();
        if (!response.ok) {
            showTemporaryAlert(result.error || '⚠️ Error setting period!', 'error');
            return;
        }
        // On successful period set, reveal the budget form container.
        document.getElementById("budget-form-container").style.display = 'block';
        prompt.style.display = 'none';
        showTemporaryAlert('Period set successfully!', 'success');
    } catch (error) {
        console.error('Error:', error);
        showTemporaryAlert('⚠️ Failed to connect to server!', 'error');
    }
});

// ----- Budget Section: Fetch and Submit Budget ----- //
// Fetch and display budgets
async function fetchBudgets() {
    try {
        const response = await fetch(`${API_URL}/get_budgets`);
        const budgets = await response.json();
        const tableBody = document.getElementById('budget-table-body');
        tableBody.innerHTML = '';
  
        budgets.forEach(budget => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${budget.year}</td>
                <td>${getMonthName(budget.month)}</td>
                <td>${budget.category}</td>
                <td>₹${budget.amount}</td>
                <td>
                    <button class="edit-btn" onclick="editBudget(${budget.budget_id})">✏️</button>
                    <button class="delete-btn" onclick="deleteBudget(${budget.budget_id})">❌</button>
                </td>
            `;
            tableBody.appendChild(row);
        });
    } catch (error) {
        showTemporaryAlert('Error fetching budgets', 'error');
    }
}

// Budget form submission (only one event listener)
document.getElementById('budget-category-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const category = document.querySelector('input[name="budget-category"]:checked')?.value;
    const amount = document.getElementById('budget-amount').value;
    const budgetIdElem = document.querySelector('input[name="budget-id"]');
    const budgetId = budgetIdElem ? budgetIdElem.value : null;

    if (!category || !amount) {
        showTemporaryAlert('Please select a category and enter an amount!', 'error');
        return;
    }

    try {
        const url = budgetId 
            ? `${API_URL}/edit_budget/${budgetId}`
            : `${API_URL}/add_budget`;

        const response = await fetch(url, {
            method: budgetId ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                category: category,
                amount: parseFloat(amount)
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to save budget');
        }

        showTemporaryAlert(`Budget ${budgetId ? 'updated' : 'added'} successfully!`, 'success');
        // Immediately update the budget list without a refresh
        fetchBudgets();
        e.target.reset();
        if (budgetIdElem) {
            budgetIdElem.remove();
        }
    } catch (error) {
        showTemporaryAlert(error.message, 'error');
    }
});

// Initially hide the budget form container
document.getElementById("budget-form-container").style.display = 'none';

// ----- Dark Mode Toggle ----- //
document.getElementById("dark-mode-toggle").addEventListener("click", function() {
    document.body.classList.toggle("dark-mode");
    const isDarkMode = document.body.classList.contains("dark-mode");
    localStorage.setItem("darkMode", isDarkMode ? "enabled" : "disabled");
});

window.addEventListener("load", function() {
    const darkMode = localStorage.getItem("darkMode");
    if (darkMode === "enabled") {
        document.body.classList.add("dark-mode");
    }
});

// Helper function to convert month number to month name
function getMonthName(monthNumber) {
    const date = new Date();
    date.setMonth(monthNumber - 1);
    return date.toLocaleString('default', { month: 'long' });
}

// Add editBudget function
async function editBudget(budgetId) {
    try {
        const response = await fetch(`${API_URL}/get_budget/${budgetId}`);
        const budget = await response.json();
        
        // Set form values
        document.querySelector(`input[value="${budget.category}"]`).checked = true;
        document.getElementById('budget-amount').value = budget.amount;
        
        // Create hidden input for budget ID
        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'budget-id';
        hiddenInput.value = budget.budget_id;
        document.getElementById('budget-category-form').appendChild(hiddenInput);
        
        // Scroll to form
        document.querySelector('.budget-form-container').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        showTemporaryAlert('Error loading budget', 'error');
    }
}

// Delete budget
async function deleteBudget(budgetId) {
    if (!confirm('Are you sure you want to delete this budget?')) return;
    try {
        const response = await fetch(`${API_URL}/delete_budget/${budgetId}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            fetchBudgets();
            showTemporaryAlert('Budget deleted successfully', 'success');
        }
    } catch (error) {
        showTemporaryAlert('Error deleting budget', 'error');
    }
}

// Helper function to show temporary alerts
function showTemporaryAlert(message, type) {
    const alertBox = document.createElement("div");
    alertBox.textContent = message;
    alertBox.className = `alert ${type}`;
    document.body.appendChild(alertBox);
    setTimeout(() => {
        alertBox.classList.add("fade-out");
        setTimeout(() => {
            if (alertBox.parentNode) {
                alertBox.parentNode.removeChild(alertBox);
            }
        }, 300);
    }, 2000);
}

// ----- Initialization ----- //
fetchCategories().then(() => {
    fetchExpenses();
    fetchStats();
    populateYearSelect();
    fetchBudgets();
});
setInterval(displayRandomMessage, 3000);
