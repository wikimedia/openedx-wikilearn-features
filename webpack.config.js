/* eslint-env node */

'use strict';

const path = require('path');

module.exports = {
    context: __dirname,
    entry: {
        Translations: './openedx_wikilearn_features/meta_translations/static/translations/js/Translations.js',
    },
    output: {
        path: path.resolve(__dirname, 'openedx_wikilearn_features/meta_translations/static/bundles'),
        filename: '[name].js',
        library: {
            type: 'window',
            name: '[name]',
        },
    },
    module: {
        rules: [
            {
                test: /\.(js|jsx)$/,
                exclude: /node_modules/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-env', '@babel/preset-react'],
                    },
                },
            },
            {
                test: /\.css$/,
                use: ['style-loader', 'css-loader'],
            },
            {
                test: /\.(png|jpe?g|gif|svg)$/i,
                type: 'asset/resource',
            },
        ],
    },
    resolve: {
        extensions: ['.js', '.jsx'],
        modules: [
            'node_modules',
            path.resolve(__dirname, 'openedx_wikilearn_features/meta_translations/static'),
        ],
    },
    optimization: {
        minimize: false, // Set to true for production builds if needed
    },
};

