/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// Random word list for generating user ID
const randomWords = [
    'alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel',
    'india', 'juliet', 'kilo', 'lima', 'mike', 'november', 'oscar', 'papa',
    'quebec', 'romeo', 'sierra', 'tango', 'uniform', 'victor', 'whiskey', 'xray',
    'yankee', 'zulu', 'amber', 'azure', 'crimson', 'emerald', 'fuchsia', 'golden',
    'ivory', 'jade', 'krypton', 'lunar', 'mint', 'nebula', 'onyx', 'prism',
    'quartz', 'ruby', 'sapphire', 'topaz', 'ultraviolet', 'violet', 'xenon', 'zenith',
    'arctic', 'blaze', 'coral', 'dusk', 'ember', 'flame', 'glacier', 'harbor',
    'island', 'jungle', 'kindle', 'meadow', 'ocean', 'peak', 'quest', 'ridge',
    'storm', 'tundra', 'valley', 'wizard', 'crystal', 'dragon', 'falcon', 'hawk'
];

/**
 * Generates a random user ID consisting of 3 random words connected with hyphens.
 * @returns {string} A random user ID in the format "word1-word2-word3"
 */
function generateRandomUserId() {
    const words = [];
    for (let i = 0; i < 2; i++) {
        const randomIndex = Math.floor(Math.random() * randomWords.length);
        words.push(randomWords[randomIndex]);
    }
    return words.join('-');
}
