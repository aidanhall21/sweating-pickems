// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyC_kYirZnmmHvvp5c8oZ9Kwiojumc-KDIE",
    authDomain: "sweating-pickems.firebaseapp.com",
    projectId: "sweating-pickems",
    storageBucket: "sweating-pickems.firebasestorage.app",
    messagingSenderId: "1018704447202",
    appId: "1:1018704447202:web:a01eb712bb1e83298c40bb",
    measurementId: "G-M788W9S0Q0"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const provider = new GoogleAuthProvider();

// Function to update UI based on auth state
function updateUI(user) {
    const userInfo = document.getElementById('user-info');
    const userName = document.getElementById('user-name');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');

    if (user) {
        userInfo.classList.remove('d-none');
        userName.textContent = user.displayName;
        loginButton.classList.add('d-none');
        logoutButton.classList.remove('d-none');
    } else {
        userInfo.classList.add('d-none');
        loginButton.classList.remove('d-none');
        logoutButton.classList.add('d-none');
    }
}

// Listen for auth state changes
onAuthStateChanged(auth, async (user) => {
    if (user) {
        // Get the ID token
        const idToken = await user.getIdToken();
        
        // Verify the token with our backend
        try {
            const response = await fetch('verify_login.php', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ token: idToken }),
            });

            if (!response.ok) {
                throw new Error('Token verification failed');
            }

            const data = await response.json();
            updateUI(user);
            
            // Dispatch custom event for auth state change
            window.dispatchEvent(new CustomEvent('authStateChanged', {
                detail: { isLoggedIn: true, user: user }
            }));
            
            // Refresh the page after successful login to update PHP session state
            // Only refresh if we're not already showing the logged-in state
            const loginButton = document.getElementById('login-button');
            const hasSubscriptionContent = document.querySelector('.btn[onclick="handleSubscribeClick()"]');
            
            if (!loginButton.classList.contains('d-none') && hasSubscriptionContent) {
                setTimeout(() => {
                    window.location.reload();
                }, 500); // Small delay to let the user see the login success
            }
        } catch (error) {
            console.error('Error verifying token:', error);
            // If verification fails, sign out the user
            await signOut(auth);
            updateUI(null);
            
            // Dispatch custom event for auth state change
            window.dispatchEvent(new CustomEvent('authStateChanged', {
                detail: { isLoggedIn: false, user: null }
            }));
        }
    } else {
        updateUI(null);
        
        // Dispatch custom event for auth state change
        window.dispatchEvent(new CustomEvent('authStateChanged', {
            detail: { isLoggedIn: false, user: null }
        }));
    }
});

// Login function
window.loginWithGoogle = async () => {
    try {
        await signInWithPopup(auth, provider);
    } catch (error) {
        console.error('Error during login:', error);
    }
};

// Logout function
window.logout = async () => {
    try {
        // Sign out from Firebase
        await signOut(auth);
        
        // Clear the session by making a request to the server
        const response = await fetch('logout.php', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            throw new Error('Failed to clear session');
        }

        // Redirect to home page after logout
        window.location.href = 'index.php';
    } catch (error) {
        console.error('Error during logout:', error);
    }
}; 