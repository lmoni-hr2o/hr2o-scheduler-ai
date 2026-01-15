const functions = require("firebase-functions");
const admin = require("firebase-admin");
const express = require("express");
const cors = require("cors");
const authMiddleware = require("./middleware/auth");
const importController = require("./controllers/importController");

admin.initializeApp();

const app = express();

// Automatically allow cross-origin requests
app.use(cors({ origin: true }));

// Parsing JSON bodies
app.use(express.json());

// Main Import Route
// Protected by HMAC Middleware
app.post("/api/v1/import-data", authMiddleware.validateHmac, importController.importData);

// Expose Express API as a single Cloud Function
exports.api = functions.https.onRequest(app);
