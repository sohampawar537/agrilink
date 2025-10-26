// Wait for the DOM to be fully loaded before running scripts
document.addEventListener("DOMContentLoaded", function() {

    // --- AI Price Suggestion ---
    const suggestPriceBtn = document.getElementById("suggest-price-btn");
    const cropNameInput = document.getElementById("crop-name");
    const priceInput = document.getElementById("price");

    if (suggestPriceBtn) {
        suggestPriceBtn.addEventListener("click", function() {
            const cropName = cropNameInput.value;
            if (!cropName) {
                alert("Please enter a crop name first.");
                return;
            }

            // Show loading state
            suggestPriceBtn.textContent = "Loading...";
            suggestPriceBtn.disabled = true;

            // Fetch the predicted price from our API
            fetch(`/api/predict-price?crop=${encodeURIComponent(cropName)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else if (data.predicted_price) {
                        priceInput.value = data.predicted_price;
                    }
                    // Restore button
                    suggestPriceBtn.textContent = "Suggest Price";
                    suggestPriceBtn.disabled = false;
                })
                .catch(error => {
                    console.error("Error fetching price prediction:", error);
                    alert("Could not fetch price suggestion.");
                    suggestPriceBtn.textContent = "Suggest Price";
                    suggestPriceBtn.disabled = false;
                });
        });
    }

    // --- Real-time Crop Search (Company Dashboard) ---
    const searchInput = document.getElementById("crop-search-input");
    const cropListContainer = document.getElementById("crop-list-container");

    if (searchInput && cropListContainer) {
        const allCards = cropListContainer.getElementsByClassName("crop-card");

        searchInput.addEventListener("keyup", function(e) {
            const searchTerm = e.target.value.toLowerCase();
            
            for (let card of allCards) {
                const cropName = card.dataset.cropName; // We set this data-* attribute in the HTML
                if (cropName.includes(searchTerm)) {
                    card.style.display = "block";
                } else {
                    card.style.display = "none";
                }
            }
        });
    }

    // --- Voice Search (Company Dashboard) ---
    const voiceSearchBtn = document.getElementById("voice-search-btn");
    if (voiceSearchBtn) {
        // Check if browser supports Speech Recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.lang = 'en-US';

            voiceSearchBtn.addEventListener("click", () => {
                voiceSearchBtn.classList.add("is-listening");
                recognition.start();
            });

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                searchInput.value = transcript;
                
                // Manually trigger the 'keyup' event to filter the list
                searchInput.dispatchEvent(new Event('keyup'));
            };

            recognition.onend = () => {
                voiceSearchBtn.classList.remove("is-listening");
            };

            recognition.onerror = (event) => {
                console.error("Speech recognition error:", event.error);
                alert("Voice recognition failed. Please try again.");
                voiceSearchBtn.classList.remove("is-listening");
            };

        } else {
            // Hide the button if the API is not supported
            voiceSearchBtn.style.display = "none";
            console.warn("Speech Recognition API not supported in this browser.");
        }
    }

    // --- Logistics Modal Logic ---
    const modal = document.getElementById("logistics-modal");
    const partnerList = document.getElementById("partner-list");
    let currentOrderId = null;

    // Function to open the modal
    function openModal(orderId) {
        currentOrderId = orderId;
        partnerList.innerHTML = "<p>Loading partners...</p>"; // Show loading state
        modal.style.display = "block";

        // Fetch partners from our API
        fetch('/api/logistics-partners')
            .then(response => response.json())
            .then(partners => {
                partnerList.innerHTML = ""; // Clear loading state
                if (partners.length === 0) {
                    partnerList.innerHTML = "<p>No logistics partners found.</p>";
                    return;
                }
                partners.forEach(partner => {
                    const item = document.createElement("li");
                    item.className = "partner-item";
                    item.innerHTML = `
                        <div class="partner-details">
                            <span class="partner-name">${partner.name}</span>
                            <span class="partner-contact">${partner.phone || 'No phone'}</span>
                            <span class.="partner-rating">Rating: ${partner.rating} ★</span>
                        </div>
                        <button class="partner-select-btn" data-partner-id="${partner.id}">Select</button>
                    `;
                    partnerList.appendChild(item);
                });
            })
            .catch(err => {
                console.error("Error fetching partners:", err);
                partnerList.innerHTML = "<p>Could not load partners. Please try again.</p>";
            });
    }

    // Function to close the modal
    function closeModal() {
        modal.style.display = "none";
        currentOrderId = null;
    }

    // Event delegation for opening the modal
    document.body.addEventListener("click", function(event) {
        if (event.target.classList.contains("arrange-transport-btn")) {
            const orderId = event.target.dataset.orderId;
            openModal(orderId);
        }
    });

    // Event delegation for selecting a partner
    partnerList.addEventListener("click", function(event) {
        if (event.target.classList.contains("partner-select-btn")) {
            const partnerId = event.target.dataset.partnerId;
            event.target.textContent = "Assigning...";
            event.target.disabled = true;

            fetch(`/order/${currentOrderId}/assign-logistics`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ partner_id: partnerId }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    closeModal();
                    // Reload the page to show the new status
                    window.location.reload(); 
                } else {
                    alert("Error: " + data.error);
                    event.target.textContent = "Select";
                    event.target.disabled = false;
                }
            })
            .catch(err => {
                console.error("Error assigning partner:", err);
                alert("An error occurred. Please try again.");
                event.target.textContent = "Select";
                event.target.disabled = false;
            });
        }
    });

    // Close modal logic
    const closeBtn = document.querySelector(".close-btn");
    if (closeBtn) {
        closeBtn.onclick = closeModal;
    }
    window.onclick = function(event) {
        if (event.target == modal) {
            closeModal();
        }
    };

});

