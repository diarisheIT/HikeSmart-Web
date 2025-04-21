// src/App.js
import React, { useState } from 'react';
import { 
  Search, ArrowRight, Sun, Cloud, CloudRain, Thermometer, 
  MapPin, BarChart2, Compass, Info, AlertCircle
} from 'react-feather';
import './App.css';

function App() {
  const [userPreference, setUserPreference] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [weatherInfo, setWeatherInfo] = useState(null);
  const [error, setError] = useState(null);
  
  const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:5000";
  
  const handleSearch = async () => {
    if (!userPreference.trim()) {
      setError("Please describe your hiking preferences");
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/recommend`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ preference: userPreference }),
      });
      
      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`);
      }
      
      const data = await response.json();
      setWeatherInfo(data.weather);
      setResults(data.recommendations);
    } catch (err) {
      setError(`Error: ${err.message}`);
      console.error('Error fetching recommendations:', err);
    } finally {
      setLoading(false);
    }
  };
  
  // Determine weather icon based on condition
  const getWeatherIcon = (condition) => {
    if (!condition) return <Cloud size={24} />;
    
    const conditionLower = condition.toLowerCase();
    if (conditionLower.includes('rain') || conditionLower.includes('shower')) {
      return <CloudRain size={24} color="#3b82f6" />;
    } else if (conditionLower.includes('sunny')) {
      return <Sun size={24} color="#f59e0b" />;
    } else {
      return <Cloud size={24} color="#6b7280" />;
    }
  };
  
  // Map difficulty to colors
  const getDifficultyColor = (difficulty) => {
    if (!difficulty) return "bg-gray-200";
    
    const diffLower = difficulty?.toLowerCase() || '';
    if (diffLower.includes('easy')) return "bg-green-500";
    if (diffLower.includes('moderate')) return "bg-yellow-500";
    if (diffLower.includes('difficult')) return "bg-red-500";
    return "bg-gray-200";
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-emerald-600 text-white p-4 shadow-md">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">HikeSmart HK</h1>
          <Info size={24} />
        </div>
      </header>
      
      {/* Search Section */}
      <section className="p-4 bg-white shadow-md">
        <div className="flex items-center bg-gray-100 rounded-full p-2 mb-4">
          <Search className="text-gray-500 ml-2" size={20} />
          <input 
            className="flex-grow bg-transparent outline-none pl-3 text-gray-800"
            placeholder="Describe your ideal hike..."
            value={userPreference}
            onChange={(e) => setUserPreference(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <button 
          className="bg-emerald-600 text-white w-full py-3 rounded-full font-medium flex items-center justify-center"
          onClick={handleSearch}
          disabled={loading}
        >
          {loading ? 'Finding Trails...' : 'Find Perfect Trails'}
          {!loading && <ArrowRight className="ml-2" size={18} />}
        </button>
      </section>
      
      {/* Error Message */}
      {error && (
        <div className="mx-4 mt-4 p-3 bg-red-50 border-l-4 border-red-500 rounded flex items-start">
          <AlertCircle size={18} className="text-red-500 mt-0.5 mr-2" />
          <span className="text-red-800">{error}</span>
        </div>
      )}
      
      {/* Weather Section */}
      {weatherInfo && (
        <section className="mx-4 mt-4 p-4 bg-white rounded-xl shadow-md">
          <h2 className="text-lg font-semibold mb-2 text-gray-800">Weather {weatherInfo.date}</h2>
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              {getWeatherIcon(weatherInfo.condition)}
              <span className="ml-2 text-gray-800">{weatherInfo.condition}</span>
            </div>
            <div className="flex items-center">
              <Thermometer size={18} className="text-red-500" />
              <span className="ml-1 text-gray-800">{weatherInfo.temp}</span>
            </div>
          </div>
          {weatherInfo.humidity && (
            <div className="mt-1 text-sm text-gray-600">
              Humidity: {weatherInfo.humidity}
            </div>
          )}
          {weatherInfo.alert && (
            <div className="mt-2 bg-yellow-100 border-l-4 border-yellow-500 p-2 text-sm">
              ⚠️ {weatherInfo.alert}
            </div>
          )}
        </section>
      )}
      
      {/* Trail Results */}
      {results && results.length > 0 && (
        <section className="p-4">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Recommended Trails</h2>
          <div className="space-y-4">
            {results.map((trail, index) => (
              <div key={index} className="bg-white rounded-xl shadow-md overflow-hidden">
                <div className="p-4">
                  {trail.description ? (
                    // Handle plain text descriptions from AI
                    <p className="text-gray-800">{trail.description}</p>
                  ) : (
                    // Handle structured data
                    <>
                      <div className="flex justify-between items-start">
                        <h3 className="font-bold text-lg text-gray-800">{trail.name}</h3>
                        <span className={`${getDifficultyColor(trail.difficulty)} text-white text-xs font-medium px-2 py-1 rounded-full`}>
                          {trail.difficulty}
                        </span>
                      </div>
                      
                      <div className="mt-3 space-y-2">
                        {trail.length && (
                          <div className="flex items-center text-gray-700">
                            <BarChart2 size={16} className="mr-2 text-emerald-600" />
                            <span>{trail.length} km</span>
                          </div>
                        )}
                        
                        {trail.station && (
                          <div className="flex items-center text-gray-700">
                            <MapPin size={16} className="mr-2 text-emerald-600" />
                            <span>{trail.station} ({trail.distance} km walk)</span>
                          </div>
                        )}
                      </div>
                      
                      {trail.website && (
                        <div className="mt-3 pt-3 border-t border-gray-100">
                          <a 
                            href={trail.website}
                            className="text-emerald-600 text-sm font-medium flex items-center"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <Compass size={16} className="mr-1" />
                            Trail Details
                            <ArrowRight size={14} className="ml-1" />
                          </a>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default App;