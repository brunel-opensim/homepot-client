import React, { useState } from "react";

const Login = () => {
    const [activeTab, setActiveTab] = useState('ENGINEER');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const handleLogin = () => {
        console.log('Login attempt:', { activeTab, email, password });
        // Add your login logic here
    };
    return (
        <div className="min-h-screen bg-black flex items-center justify-center p-4">
            {/* Login Card */}
            <div className="w-full max-w-md">
                <div className="bg-gray-900/90 backdrop-blur-sm border border-gray-700/50 rounded-lg p-8 shadow-2xl">
                {/* Header */}
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-bold text-white mb-6 tracking-wider">
                    HOMEPOT
                    </h1>
                    
                    {/* Tab Selector */}
                    <div className="flex rounded-lg gap-4 overflow-hidden mb-6">
                    <button
                        type="button"
                        onClick={() => setActiveTab("ENGINEER")}
                        className={`flex-1 py-3 px-6 text-sm font-semibold rounded-lg transition-all duration-200 ${
                            activeTab === "ENGINEER"
                            ? "bg-primary text-secondary border border-secondary" // Neon teal glow
                            : "bg-gray-800 text-gray-400 hover:text-gray-300 hover:bg-gray-700"
                        }`}
                        >
                        ENGINEER
                        </button>

                        <button
                        type="button"
                        onClick={() => setActiveTab("CLIENT")}
                        className={`flex-1 py-3 px-6 text-sm font-semibold rounded-lg transition-all duration-200 ${
                            activeTab === "CLIENT"
                            ? "bg-primary text-secondary border border-secondary"
                            : "bg-gray-800 text-gray-400 hover:text-gray-300 hover:bg-gray-700"
                        }`}
                        >
                        CLIENT
                        </button>

                    </div>
                </div>

                {/* Login Form */}
                <div className="space-y-6">
                    {/* Email Input */}
                    <div>
                    <input
                        type="text"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Email or username"
                        className="w-full px-4 py-4 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all duration-200"
                    />
                    </div>

                    {/* Password Input */}
                    <div>
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Password"
                        className="w-full px-4 py-4 bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all duration-200"
                    />
                    </div>

                    {/* SSO Link */}
                    <div className="text-center">
                    <button
                        type="button"
                        className="text-teal-400 hover:text-teal-300 text-sm transition-colors duration-200"
                    >
                        Sign in with SSO
                    </button>
                    </div>

                    {/* Login Button */}
                    <button
                    type="button"
                    onClick={handleLogin}
                    className="w-full bg-accent hover:bg-teal-800 text-white font-medium py-4 px-6 rounded-lg transition-all duration-200 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 focus:ring-offset-gray-900"
                    >
                    Log In
                    </button>
                </div>

                {/* Two-factor Authentication Notice */}
                <div className="mt-6 text-center">
                    <p className="text-gray-400 text-sm">
                    Two-factor authentication required
                    </p>
                    <p className="text-gray-400 text-sm">
                    for Engineers
                    </p>
                </div>

                {/* Footer */}
                <div className="mt-8 text-center">
                    <p className="text-gray-500 text-xs">
                    Powered by HOMEPOT Unified Client
                    </p>
                </div>
                </div>
            </div>
        </div>
    )
}

export default Login;