// Checks paste_import.js without a browser:  node tests/test_paste.mjs
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const ctx={};vm.createContext(ctx);
vm.runInContext(readFileSync(new URL('../paste_import.js',import.meta.url),'utf8'),ctx);
const convert=ctx.pastedTextToCsv;
const H='"manufacturer","filament_type","color_name","quantity"';
const cases=[
 ['rows copied from Google Sheets without a header','Bambu Lab\tABS\tBlack\t4\nCookiecad\tTPU 95A\tPink Pearl\t2\n',
  H+'\r\n"Bambu Lab","ABS","Black","4"\r\n"Cookiecad","TPU 95A","Pink Pearl","2"\r\n'],
 ['rows with the header and a Status column','manufacturer\tfilament_type\tcolor_name\tquantity\tStatus\r\nBambu Lab\tABS\tBlack\t4\t✓ OK\r\n',
  '"manufacturer","filament_type","color_name","quantity","Status"\r\n"Bambu Lab","ABS","Black","4","✓ OK"\r\n'],
 ['Status column dropped when there is no header','Bambu Lab\tABS\tBlack\t4\t✓ OK',
  H+'\r\n"Bambu Lab","ABS","Black","4"\r\n'],
 ['quoted cell containing a quote','Cookiecad\t"Say ""hi"""\tBlue\t1\n',
  H+'\r\n"Cookiecad","Say ""hi""","Blue","1"\r\n'],
 ['blank lines ignored','\n\nBambu Lab\tABS\tBlack\t1\n\n',H+'\r\n"Bambu Lab","ABS","Black","1"\r\n'],
 ['plain CSV gets a header','Bambu Lab,ABS,Black,1','manufacturer,filament_type,color_name,quantity\r\nBambu Lab,ABS,Black,1'],
 ['plain CSV with header is unchanged','manufacturer,filament_type,color_name,quantity\nBambu Lab,ABS,Black,1\n','manufacturer,filament_type,color_name,quantity\nBambu Lab,ABS,Black,1\n'],
];
for(const [name,input,expected] of cases){assert.equal(convert(input),expected,name);console.log('PASS',name);}
assert.throws(()=>convert('   \n'),/Paste at least one row/);console.log('PASS empty paste rejected');
