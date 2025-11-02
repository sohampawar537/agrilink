document.addEventListener('DOMContentLoaded', function() {

    // --- Voice Search Functionality ---
    const voiceSearchBtn = document.getElementById('voice-search-btn');
    const searchBar = document.getElementById('search-bar');
    const micIcon = document.getElementById('mic-icon');

    if (voiceSearchBtn && searchBar && micIcon) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.lang = 'en-US'; // Can be changed

            voiceSearchBtn.addEventListener('click', () => {
                if (micIcon.classList.contains('listening')) {
                    recognition.stop();
                    micIcon.classList.remove('listening');
                } else {
                    recognition.start();
                    micIcon.classList.add('listening');
                }
            });

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                searchBar.value = transcript;
                // Trigger the search filter
                filterCrops();
            };

            recognition.onend = () => {
                micIcon.classList.remove('listening');
            };

            recognition.onerror = (event) => {
                console.error("Speech recognition error", event.error);
                micIcon.classList.remove('listening');
            };
        } else {
            // Hide button if API is not supported
            voiceSearchBtn.style.display = 'none';
        }
    }

    // --- Text Search Filter Functionality ---
    if (searchBar) {
        searchBar.addEventListener('keyup', filterCrops);
    }

    function filterCrops() {
        const filter = searchBar.value.toLowerCase();
        const cropCards = document.querySelectorAll('.crop-card');
        
        cropCards.forEach(card => {
            const cropName = card.querySelector('h4').textContent.toLowerCase();
            if (cropName.includes(filter)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    // --- AI Price Suggestion Functionality ---
    const suggestPriceBtn = document.getElementById('suggest-price-btn');
    if (suggestPriceBtn) {
        suggestPriceBtn.addEventListener('click', async (e) => {
            e.preventDefault(); // Prevent form submission
            const cropNameField = document.getElementById('crop-name-field');
            const cropPriceField = document.getElementById('crop-price-field');
            const cropName = cropNameField.value;

            if (!cropName) {
                alert('Please enter a Crop Name first.');
                return;
            }

            suggestPriceBtn.textContent = '...';
            suggestPriceBtn.disabled = true;

            try {
                const response = await fetch(`/api/predict-price/${cropName}`);
                const data = await response.json();

                if (response.ok) {
                    cropPriceField.value = data.predicted_price;
                } else {
                    alert(data.error || 'Could not fetch price.');
                }
            } catch (error) {
                console.error('Error fetching price:', error);
                alert('An error occurred. Please try again.');
            } finally {
                suggestPriceBtn.textContent = 'Suggest Price';
                suggestPriceBtn.disabled = false;
            }
        });
    }

    // --- Logistics Modal Functionality ---
    const modal = document.getElementById("logisticsModal");
    const modalCloseBtn = document.querySelector(".modal-close");
    const partnerList = document.getElementById("logistics-partner-list");
    
    // Open modal
    document.querySelectorAll('.btn-arrange-transport').forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const orderId = e.target.dataset.orderId;
            modal.dataset.currentOrderId = orderId; // Store orderId in modal
            
            // Clear previous list
            partnerList.innerHTML = "<li>Loading partners...</li>";
            modal.style.display = "block";

            // Fetch partners
            try {
                const response = await fetch('/api/logistics-partners');
                if (!response.ok) throw new Error('Network response was not ok');
                const partners = await response.json();
                
                partnerList.innerHTML = ""; // Clear "Loading"
                if (partners.length === 0) {
                    partnerList.innerHTML = "<li>No logistics partners found.</li>";
                    return;
                }
                
                partners.forEach(partner => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <div>
                            <strong>${partner.name}</strong><br>
                            <small>Vehicles: ${partner.vehicles} | ${partner.email}</small>
                        </div>
                        <button class="btn-select-partner" data-partner-id="${partner.id}">Select</button>
                    `;
                    partnerList.appendChild(li);
                });

            } catch (error) {
                console.error('Error fetching partners:', error);
                partnerList.innerHTML = `<li>Error loading partners. Please try again.</li>`;
            }
        });
    });

    // Close modal
    if (modalCloseBtn) {
        modalCloseBtn.onclick = function() {
            modal.style.display = "none";
        }
    }
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    }

    // Handle partner selection
    partnerList.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-select-partner')) {
            const partnerId = e.target.dataset.partnerId;
            const orderId = modal.dataset.currentOrderId;
            
            e.target.textContent = '...';
            e.target.disabled = true;

            try {
                const response = await fetch(`/order/${orderId}/assign-logistics`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ partner_id: partnerId })
                });

                const data = await response.json();
                
                if (response.ok && data.success) {
                    modal.style.display = "none";
                    // Reload the page to show the updated status
                    window.location.reload();
                } else {
                    alert(data.error || 'Could not assign partner.');
                    e.target.textContent = 'Select';
                    e.target.disabled = false;
                }
            } catch (error) {
                console.error('Error assigning partner:', error);
                alert('An error occurred. Please try again.');
                e.target.textContent = 'Select';
                e.target.disabled = false;
            }
        }
    });

});

